/*
 * Copyright 2017 Intel Corporation
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * ------------------------------------------------------------------------------
 */

//! Tools for submitting batch lists of signed batches to Sawtooth endpoints

use std::cell::RefCell;
use std::error;
use std::fmt;
use std::io::Read;
use std::iter::Cycle;
use std::rc::Rc;
use std::sync::mpsc;
use std::sync::Arc;
use std::sync::Mutex;
use std::thread;
use std::time;
use std::vec::IntoIter;

use futures::{Future, Stream};
use hyper::client::{Client, HttpConnector, Request};
use hyper::header::{ContentLength, ContentType};
use hyper::Method;
use protobuf;
use protobuf::Message;
use tokio_core::reactor::{Core, Interval};
use tokio_timer;

use sawtooth_sdk::messages::batch::Batch;
use sawtooth_sdk::messages::batch::BatchList;

use batch_gen::{BatchResult, BatchingError};
use batch_map::BatchMap;
use source::LengthDelimitedMessageSource;
use workload;

/// Populates a channel from a stream of length-delimited batches.
/// Starts one workload submitter of the appropriate type (http, zmq)
/// per target. Workload submitters consume from the channel at
/// the configured rate until the channel is exhausted.
pub fn submit_signed_batches(
    reader: &mut Read,
    target: String,
    rate: usize,
) -> Result<(), BatchReadingError> {
    let (sender, receiver) = mpsc::channel();
    let receiver = Arc::new(Mutex::new(receiver));

    let submit_thread = thread::spawn(move || {
        http_submitter(&target, rate as u64, &receiver);
    });

    let mut feeder = BatchListFeeder::new(reader);

    loop {
        match feeder.next() {
            Some(Ok(batch_list)) => {
                sender.send(Some(batch_list)).unwrap();
            }
            None => {
                sender.send(None).unwrap();
                break;
            }
            Some(Err(err)) => return Err(err),
        }
    }

    submit_thread.join().unwrap();

    Ok(())
}

pub fn http_submitter(
    target: &str,
    rate: u64,
    receiver: &Arc<Mutex<mpsc::Receiver<Option<BatchList>>>>,
) {
    let mut core = Core::new().unwrap();

    let client = Client::configure()
        .connector(HttpConnector::new(1, &core.handle()))
        .keep_alive(true)
        .build(&core.handle());

    let timer = tokio_timer::wheel()
        .tick_duration(time::Duration::new(0, 1_000_000))
        .build();

    // Define a target timeslice (how often to submit batches) based
    // on number of nanoseconds in a second divided by rate
    let timeslice = time::Duration::new(0, 1_000_000_000 / rate as u32);

    let mut uri = target.to_string();
    uri.push_str("/batches");

    let mut count = 0;
    let mut last_count = 0;
    let mut last_time = time::Instant::now();
    let mut last_trace_time = time::Instant::now();

    while let Some(mut batch_list) = receiver.lock().unwrap().recv().unwrap() {
        // Set the trace flag on a batch about once every 5 seconds
        if (time::Instant::now() - last_trace_time).as_secs() > 5 {
            batch_list.mut_batches()[0].trace = true;
            last_trace_time = time::Instant::now();
        }

        let bytes = batch_list.write_to_bytes().unwrap();

        let mut req = Request::new(Method::Post, uri.parse().unwrap());
        req.headers_mut().set(ContentType::octet_stream());
        req.headers_mut().set(ContentLength(bytes.len() as u64));
        req.set_body(bytes);

        let work = client.request(req).and_then(|_| {
            count += 1;

            if count % rate == 0 {
                let log_duration = time::Instant::now() - last_time;
                let log_duration_flt =
                    log_duration.as_secs() as f64 + f64::from(log_duration.subsec_nanos()) * 1e-9;

                println!(
                    "target: {} target rate: {} count: {} effective rate: {} per sec",
                    target,
                    rate,
                    count,
                    (count - last_count) as f64 / log_duration_flt
                );

                last_count = count;
                last_time = time::Instant::now();
            }

            Ok(())
        });

        let request_time = time::Instant::now();
        core.run(work).unwrap();
        let runtime = time::Instant::now() - request_time;

        if let Some(sleep_duration) = timeslice.checked_sub(runtime) {
            let sleep = timer.sleep(sleep_duration);
            sleep.wait().unwrap();
        }
    }
}

/// Run a continuous load of the BatchLists that are generated by BatchListIter.
pub fn run_workload(
    batch_list_iter: &mut Iterator<Item = BatchListResult>,
    time_to_wait: u32,
    update_time: u32,
    targets: Vec<String>,
    basic_auth: &Option<String>,
) -> Result<(), workload::WorkloadError> {
    let mut core = Core::new().unwrap();
    let handle = core.handle();
    let client = Rc::new(Client::configure().build(&handle));
    let counter = Rc::new(workload::HTTPRequestCounter::new());

    let mut urls: Cycle<IntoIter<String>> = targets.into_iter().cycle();

    let batch_map = Rc::new(RefCell::new(BatchMap::new()));
    let batch_map_clone = Rc::clone(&batch_map);

    let batches = Rc::new(RefCell::new(Vec::new()));
    let batches_clone = Rc::clone(&batches);

    let interval = Interval::new(time::Duration::new(0, time_to_wait), &handle).unwrap();
    let mut log_time = time::Instant::now();
    let stream = interval
        .map_err(workload::WorkloadError::from)
        .map(|_: ()| -> Result<(), workload::WorkloadError> {
            let counter_clone = Rc::clone(&counter);
            workload::log(&counter_clone, &mut log_time, update_time)
        }).map(move |_| -> Result<BatchList, workload::WorkloadError> {
            let batch_map = Rc::clone(&batch_map_clone);
            let batches_clone = Rc::clone(&batches_clone);
            workload::get_next_batchlist(batch_list_iter, &batch_map, &batches_clone)
        }).map(|batch_list: Result<BatchList, workload::WorkloadError>| {
            let basic_auth_c = basic_auth.clone();
            let urls_c = &mut urls;
            workload::form_request_from_batchlist(urls_c, batch_list, &basic_auth_c)
        }).map_err(workload::WorkloadError::from)
        .and_then(
            |req: Result<(Request, Option<String>), workload::WorkloadError>| {
                let handle_clone = handle.clone();
                let client_clone = Rc::clone(&client);
                let counter_clone = Rc::clone(&counter);
                let batches_clone = Rc::clone(&batches);
                workload::make_request(
                    &client_clone,
                    &handle_clone,
                    counter_clone,
                    Rc::clone(&batch_map),
                    batches_clone,
                    req,
                )
            },
        ).for_each(|_| Ok(()));

    core.run(stream)
}

type BatchSource<'a> = LengthDelimitedMessageSource<'a, Batch>;

/// Errors that may occur during the reading of batches.
#[derive(Debug)]
pub enum BatchReadingError {
    MessageError(protobuf::ProtobufError),
    BatchingError(BatchingError),
    UnknownError,
}

impl From<protobuf::ProtobufError> for BatchReadingError {
    fn from(err: protobuf::ProtobufError) -> Self {
        BatchReadingError::MessageError(err)
    }
}

impl fmt::Display for BatchReadingError {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match *self {
            BatchReadingError::MessageError(ref err) => {
                write!(f, "Error occurred reading messages: {}", err)
            }
            BatchReadingError::BatchingError(ref err) => {
                write!(f, "Error creating the batch: {}", err)
            }
            BatchReadingError::UnknownError => write!(f, "There was an unknown batching error."),
        }
    }
}

impl error::Error for BatchReadingError {
    fn description(&self) -> &str {
        match *self {
            BatchReadingError::MessageError(ref err) => err.description(),
            BatchReadingError::BatchingError(ref err) => err.description(),
            BatchReadingError::UnknownError => "There was an unknown batch error.",
        }
    }

    fn cause(&self) -> Option<&error::Error> {
        match *self {
            BatchReadingError::MessageError(ref err) => Some(err),
            BatchReadingError::BatchingError(ref err) => Some(err),
            BatchReadingError::UnknownError => Some(&BatchReadingError::UnknownError),
        }
    }
}

/// Produces signed batches from a length-delimited source of Transactions.
pub struct BatchListFeeder<'a> {
    batch_source: BatchSource<'a>,
}

/// Resulting BatchList or error.
pub type BatchListResult = Result<BatchList, BatchReadingError>;

impl<'a> BatchListFeeder<'a> {
    /// Creates a new `BatchListFeeder` with a given Batch source
    pub fn new(source: &'a mut Read) -> Self {
        let batch_source = LengthDelimitedMessageSource::new(source);
        BatchListFeeder { batch_source }
    }
}

impl<'a> Iterator for BatchListFeeder<'a> {
    type Item = BatchListResult;

    /// Gets the next Batch.
    /// `Ok(None)` indicates that the underlying source has been consumed.
    fn next(&mut self) -> Option<Self::Item> {
        let batches = match self.batch_source.next(1) {
            Ok(batches) => batches,
            Err(err) => return Some(Err(BatchReadingError::MessageError(err))),
        };

        if batches.is_empty() {
            return None;
        }

        // Construct a BatchList out of the read batches
        let mut batch_list = BatchList::new();
        batch_list.set_batches(protobuf::RepeatedField::from_vec(batches));

        Some(Ok(batch_list))
    }
}

pub struct InfiniteBatchListIterator<'a> {
    batches: &'a mut Iterator<Item = BatchResult>,
}

impl<'a> InfiniteBatchListIterator<'a> {
    pub fn new(batches: &'a mut Iterator<Item = BatchResult>) -> Self {
        InfiniteBatchListIterator { batches }
    }
}

impl<'a> Iterator for InfiniteBatchListIterator<'a> {
    type Item = BatchListResult;

    fn next(&mut self) -> Option<BatchListResult> {
        let batch = match self.batches.next() {
            Some(Ok(batch)) => batch,
            Some(Err(err)) => return Some(Err(BatchReadingError::BatchingError(err))),
            None => return None,
        };

        let batches = vec![batch];
        let mut batch_list = BatchList::new();
        batch_list.set_batches(protobuf::RepeatedField::from_vec(batches));
        Some(Ok(batch_list))
    }
}
