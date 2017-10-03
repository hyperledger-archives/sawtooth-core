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

extern crate protobuf;
extern crate hyper;
extern crate tokio_core;
extern crate tokio_timer;
extern crate futures;

use std::error;
use std::fmt;
use std::io::Read;
use std::thread;
use std::time;
use std::sync::mpsc;
use std::sync::Arc;
use std::sync::Mutex;

use self::tokio_core::reactor::Core;
use self::hyper::Method;
use self::hyper::client::{HttpConnector, Client, Request};
use self::hyper::header::{ContentType, ContentLength};
use self::futures::Future;

use sawtooth_sdk::messages::batch::Batch;
use sawtooth_sdk::messages::batch::BatchList;
use self::protobuf::Message;

use source::LengthDelimitedMessageSource;

/// Populates a channel from a stream of length-delimited batches.
/// Starts one workload submitter of the appropriate type (http, zmq)
/// per target. Workload submitters consume from the channel at
/// the configured rate until the channel is exhausted.
pub fn submit_signed_batches<'a>(reader: &'a mut Read, target: String, rate: usize)
    -> Result<(), BatchReadingError>
{
    let (sender, receiver) = mpsc::channel();
    let receiver = Arc::new(Mutex::new(receiver));

    let submit_thread = thread::spawn(move || {
        http_submitter(target, rate as u64, receiver);
    });

    let mut feeder = BatchListFeeder::new(reader);

    loop {
        match feeder.next_batch_list() {
            Ok(Some(batch_list)) => {
                sender.send(Some(batch_list)).unwrap();
            },
            Ok(None) => {
                sender.send(None).unwrap();
                break;
            },
            Err(err) => return Err(err),
        }
    }

    submit_thread.join().unwrap();

    Ok(())
}

pub fn http_submitter(target: String, rate: u64, receiver: Arc<Mutex<mpsc::Receiver<Option<BatchList>>>>)
{
    let mut core = Core::new().unwrap();

    let client = Client::configure()
                     .connector(HttpConnector::new(1, &core.handle()))
                     .keep_alive(true)
                     .build(&core.handle());

    let timer = tokio_timer::wheel()
                    .tick_duration(time::Duration::new(0, 1000000))
                    .build();

    /// Define a target timeslice (how often to submit batches) based
    /// on number of nanoseconds in a second divided by rate
    let timeslice = time::Duration::new(0, 1000000000/rate as u32);

    let mut uri = target.clone();
    uri.push_str("/batches");

    let mut count = 0;
    let mut last_count = 0;
    let mut last_time = time::Instant::now();
    let mut last_trace_time = time::Instant::now();

    loop {
        match receiver.lock().unwrap().recv().unwrap() {
            Some(mut batch_list) => {
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
                    count = count + 1;

                    if count % rate == 0 {
                        let log_duration = time::Instant::now() - last_time;
                        let log_duration_flt = log_duration.as_secs() as f64 + log_duration.subsec_nanos() as f64 * 1e-9;

                        println!("target: {} target rate: {} count: {} effective rate: {} per sec",
                                 target,
                                 rate,
                                 count,
                                 (count - last_count) as f64/log_duration_flt);

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
            },
            None => break
        }
    }
}

type BatchSource<'a> = LengthDelimitedMessageSource<'a, Batch>;

/// Errors that may occur during the reading of batches.
#[derive(Debug)]
pub enum BatchReadingError {
    MessageError(protobuf::ProtobufError),
}

impl fmt::Display for BatchReadingError {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match *self {
            BatchReadingError::MessageError(ref err) =>
                write!(f, "Error occurred reading messages: {}", err),
        }
    }
}

impl error::Error for BatchReadingError {
    fn description(&self) -> &str {
        match *self {
            BatchReadingError::MessageError(ref err) => err.description(),
        }
    }

    fn cause(&self) -> Option<&error::Error> {
        match *self {
            BatchReadingError::MessageError(ref err) => Some(err),
        }
    }
}

/// Produces signed batches from a length-delimited source of Transactions.
pub struct BatchListFeeder<'a> {
    batch_source: BatchSource<'a>,
}

/// Resulting BatchList or error.
pub type BatchListResult = Result<Option<BatchList>, BatchReadingError>;

impl<'a> BatchListFeeder<'a> {

    /// Creates a new `BatchListFeeder` with a given Batch source
    /// TODO put channel here?
    pub fn new(source: &'a mut Read) -> Self {
        let batch_source = LengthDelimitedMessageSource::new(source);
        BatchListFeeder {
            batch_source,
        }
    }

    /// Gets the next Batch.
    /// `Ok(None)` indicates that the underlying source has been consumed.
    pub fn next_batch_list(&mut self) -> BatchListResult {
        let batches = match self.batch_source.next(1) {
            Ok(batches) => batches,
            Err(err) => return Err(BatchReadingError::MessageError(err)),
        };

        if batches.len() == 0 {
            return Ok(None);
        }

        /// Construct a BatchList out of the read batches
        let mut batch_list = BatchList::new();
        batch_list.set_batches(protobuf::RepeatedField::from_vec(batches));

        Ok(Some(batch_list))
    }
}
