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

extern crate chrono;
extern crate protobuf;
extern crate hyper;
extern crate serde;
extern crate serde_json;
extern crate tokio_core;
extern crate tokio_timer;
extern crate futures;

use std::error;
use std::fmt;
use std::io::Read;
use std::io;
use std::thread;
use std::time;
use std::str::from_utf8;
use std::str::FromStr;
use std::str::Utf8Error;
use std::sync::atomic::{AtomicUsize, AtomicBool, Ordering};
use std::sync::mpsc;
use std::sync::Arc;
use std::sync::Mutex;

use self::tokio_core::reactor::{Core, Interval};
use self::hyper::Chunk;
use self::hyper::Error as HyperError;
use self::hyper::error::UriError;
use self::hyper::Method;
use self::hyper::client::{HttpConnector, Client, Request};
use self::hyper::header::{ContentType, ContentLength};
use self::hyper::Uri;
use self::futures::{Future, Stream};
use self::futures::future;

use sawtooth_sdk::messages::batch::Batch;
use sawtooth_sdk::messages::batch::BatchList;
use self::protobuf::Message;

use batch_gen::{BatchResult, BatchingError};
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
        match feeder.next() {
            Some(Ok(batch_list)) => {
                sender.send(Some(batch_list)).unwrap();
            },
            None => {
                sender.send(None).unwrap();
                break;
            },
            Some(Err(err)) => return Err(err),
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

// Returned by the HTTP Post to /batches on the REST Api.
#[derive(Debug)]
#[derive(Deserialize)]
struct Link {
    link: String,
}

// A BatchStatus for one batch; returned by the GET /batch_statuses route.
#[derive(Deserialize)]
struct BatchStatus {
    status: String,
}

// The full response from GET /batch_statuses.
#[derive(Deserialize)]
struct BatchStatusesResponse {
    data: Vec<BatchStatus>,
}

#[derive(Debug)]
#[derive(Deserialize)]
struct RestApiErrorResponse {
    error : ErrorResponse,
}

#[derive(Debug)]
#[derive(Deserialize)]
struct ErrorResponse {
    code: u32,
    message: String,
    title: String,
}

struct HTTPRequestCounter {
    sent_count: AtomicUsize,
    committed_count: AtomicUsize,
    invalid_count: AtomicUsize,
    queue_full_count: AtomicUsize,

    url_error: AtomicBool,
}

impl HTTPRequestCounter {


    fn new() -> Self {
        HTTPRequestCounter {
            sent_count: AtomicUsize::new(0),
            committed_count: AtomicUsize::new(0),
            invalid_count: AtomicUsize::new(0),
            queue_full_count: AtomicUsize::new(0),

            url_error: AtomicBool::new(false),
         }
     }

    fn increment_committed(&self) {
        self.committed_count.fetch_add(1, Ordering::Relaxed);
    }

    fn increment_sent(&self) {
        self.sent_count.fetch_add(1, Ordering::Relaxed);
    }

    fn increment_invalid(&self) {
        self.invalid_count.fetch_add(1, Ordering::Relaxed);
    }

    fn increment_queue_full(&self) {
        self.queue_full_count.fetch_add(1, Ordering::Relaxed);
    }

    fn url_error(&self) {
        self.url_error.store(true, Ordering::Relaxed);
    }

    fn has_url_error(&self) -> bool {
        self.url_error.load(Ordering::Relaxed)
    }

    fn log(&self, seconds: u64, nanoseconds: u32) {
        let update = seconds as f64 + nanoseconds as f64 * 1e-9;
        println!("{} Batches/s {:.3} Committed/s {:.3} Invalid/s {:.3}",
            self,
            self.sent_count.load(Ordering::Relaxed) as f64 / update,
            self.committed_count.load(Ordering::Relaxed) as f64 / update,
            self.invalid_count.load(Ordering::Relaxed) as f64 / update);
        
        self.sent_count.store(0, Ordering::Relaxed);
        self.committed_count.store(0, Ordering::Relaxed);
        self.invalid_count.store(0, Ordering::Relaxed);
        self.queue_full_count.store(0, Ordering::Relaxed);
    }
}


impl fmt::Display for HTTPRequestCounter {

    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        let time = chrono::Utc::now();
        write!(f, "{0}, Sent: {1}, Committed {2}/{1}, Invalid {3}/{1} Queue Full {4}/{1}",
               time.format("%h-%d-%Y %H:%M:%S%.3f").to_string(),
               self.sent_count.load(Ordering::Relaxed),
               self.committed_count.load(Ordering::Relaxed),
               self.invalid_count.load(Ordering::Relaxed),
               self.queue_full_count.load(Ordering::Relaxed))
    }
}

/// Run a continuous load of the BatchLists that are generated by BatchListIter.
pub fn run_workload(batch_list_iter: &mut Iterator<Item = BatchListResult>, time_to_wait: u32, update_time: u32, targets: Vec<String>)
    -> Result<(), WorkloadError>
{
    let mut core = Core::new().unwrap();
    let handle = core.handle();
    let handle_clone = handle.clone();
    let client = Client::configure()
        .keep_alive(true)
        .keep_alive_timeout(Some(time::Duration::new(100, 0)))
        .build(&handle);
    let client_clone = client.clone();

    let mut urls = targets.into_iter().cycle();

    let mut last_log = time::Instant::now();

    let counter = Arc::new(HTTPRequestCounter::new());
    let counter_l = counter.clone();
    let counter_c = counter.clone();
    let counter_i = counter.clone();
    let counter_q = counter.clone();
    let counter_s = counter.clone();
    let counter_e = counter.clone();

    let stream : Interval = Interval::new(time::Duration::new(0, time_to_wait), &handle).unwrap();
    let stream_work = stream
        .map(move |_| {
            if counter_l.has_url_error() {
                return Err(WorkloadError::from(io::Error::new(io::ErrorKind::Other, "Could not access url")))
            }

            let log_time = time::Instant::now() - last_log;
            if log_time.as_secs() as u32 >= update_time {
                counter_l.log(log_time.as_secs(), log_time.subsec_nanos());
                last_log = time::Instant::now();
            }
            match batch_list_iter.next() {
                Some(Ok(batch_list)) => Ok(batch_list),
                Some(Err(err)) => return Err(WorkloadError::from(err)),
                None => return Err(WorkloadError::NoBatchError),
            }
        }).map_err(|err| WorkloadError::from(err))
        .map(|batch_list| {
            let mut batch_url = urls.next().unwrap();
            batch_url.push_str("/batches");

            let bytes = batch_list?.write_to_bytes()?;
            let mut req = Request::new(Method::Post, Uri::from_str(batch_url.as_ref())?);
            let content_len = bytes.len() as u64;
            req.set_body(bytes);
            req.headers_mut().set(ContentType::octet_stream());
            req.headers_mut().set(ContentLength(content_len));
            Ok(req)
        }).and_then(|req: Result<Request, WorkloadError>| {
            match req {
                Ok(req) => {
                let counter_cc = counter_c.clone();
                let counter_qq = counter_q.clone();
                let counter_ii = counter_i.clone();
                let counter_ee = counter_e.clone();
                let handle_clone_2 = handle_clone.clone();
                let handle_clone_3 = handle_clone.clone();
                let client_clone_c = client_clone.clone();
                counter_s.increment_sent();
                let work = client.request(req)
                    .then(move |response| {
                        match response {
                            Ok(response) => Some(response.body().concat2()),
                            Err(_) => {
                                counter_ee.url_error();
                                None
                            },
                        }
                    })
                    .map(move |body| {
                        match body {
                            Some(body) => {
                                let counter_qqq = counter_qq.clone();
                                match from_utf8(&body) {
                                    Ok(s) => {
                                        let link = serde_json::from_str::<Link>(s);
                                        match link {
                                            Ok(link) => {
                                                let mut l = link.link;
                                                l.push_str("&wait=100");
                                                let uri = Uri::from_str(l.as_ref())?;
                                                return Ok(uri)
                                            },
                                            Err(_) => (), // When the rest api returns the Error json -- for example with Queue full message.
                                        }

                                    },
                                    Err(err) => println!("{}", err),
                                }
                                match from_utf8(&body) {
                                    Ok(s) => {
                                        let rest_api_error = serde_json::from_str::<RestApiErrorResponse>(s)?;
                                            if rest_api_error.error.code == 31 {
                                                counter_qqq.increment_queue_full();
                                            } else {
                                                println!("{:?}", rest_api_error);
                                            }
                                            return Err(WorkloadError::UnknownRestApiError)
                                    },
                                    Err(err) => {
                                        println!("Error converting UTF8: {}", err);
                                        return Err(WorkloadError::Utf8Error(err))
                                    },
                                }
                            },

                            None => Err(WorkloadError::UnknownRestApiError),
                    }})
                    .and_then(move |uri: Result<Uri, WorkloadError> | {
                        match uri {
                            Ok(uri) => {
                                let get_status = client_clone_c.get(uri)
                                    .and_then(|response| response.body().concat2())
                                    .map(|body: Chunk| {
                                        let batch_statuses_response = serde_json::from_str(from_utf8(&body.to_vec())?)?;
                                        Ok(batch_statuses_response)
                                    })
                                    .map(move |batch_statuses_response: Result<BatchStatusesResponse, WorkloadError>| {
                                        let counter_ccc = counter_cc.clone();
                                        let counter_iii = counter_ii.clone();
                                        match batch_statuses_response?.data.get(0) {
                                            Some(batch_status) => {
                                                if batch_status.status == "COMMITTED" {
                                                    counter_ccc.increment_committed();
                                                } else if batch_status.status == "INVALID" {
                                                    counter_iii.increment_invalid();
                                                }
                                            },
                                            None => println!("Batch status came back with no status."),
                                        };
                                        Ok(())
                                    }).and_then(|_: Result<(), WorkloadError>| future::ok(()) ).map_err(|_| ());

                                    Ok(handle_clone_2.spawn(get_status))
                            },
                            Err(_) => {Ok(())},
                        }
                    }).and_then(|_| future::ok(()) ).map_err(|_| () );
                Ok(handle_clone_3.spawn(work))
            },
            
            Err(err) => Err(err),
            }
            }).for_each(|_| future::ok(())).map_err(|err| WorkloadError::from(err));

    core.run(stream_work)
}

#[derive(Debug)]
pub enum WorkloadError {
    HttpError(HyperError),
    Utf8Error(Utf8Error),
    UriError(UriError),
    JsonError(serde_json::Error),
    ProtobufError(protobuf::ProtobufError),
    BatchReadingError(BatchReadingError),
    IoError(io::Error),
    NoBatchError,
    UnknownRestApiError,
}

impl fmt::Display for WorkloadError {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match *self {
            WorkloadError::HttpError(ref err) => write!(f, "An http error occurred: {}", err),
            WorkloadError::Utf8Error(ref err) => write!(f, "A utf8 decoding error occurred: {}", err),
            WorkloadError::UriError(ref err) => write!(f, "A uri error occurred: {}", err),
            WorkloadError::IoError(ref err) => write!(f, "An io error occurred: {}", err),
            WorkloadError::JsonError(ref err) => write!(f, "A json parsing error occurred: {}", err),
            WorkloadError::ProtobufError(ref err) => write!(f, "A protobuf error occurred: {}", err),
            WorkloadError::BatchReadingError(ref err) => write!(f, "A generic batch reading error occurred: {}", err),
            WorkloadError::NoBatchError => write!(f, "An unknown error occurred resulting in a lack of a batch to send"),
            WorkloadError::UnknownRestApiError => write!(f, "This error produced a rest api error that should be handled."),
        }
    }
}

impl error::Error for WorkloadError {

    fn cause(&self) -> Option<&error::Error> {
        match *self {
            WorkloadError::HttpError(ref err) => err.cause(),
            WorkloadError::Utf8Error(ref err) => err.cause(),
            WorkloadError::UriError(ref err) => err.cause(),
            WorkloadError::IoError(ref err) => err.cause(),
            WorkloadError::JsonError(ref err) => err.cause(),
            WorkloadError::ProtobufError(ref err) => err.cause(),
            WorkloadError::BatchReadingError(ref err) => err.cause(),
            WorkloadError::NoBatchError => Some(&WorkloadError::NoBatchError),
            WorkloadError::UnknownRestApiError => Some(&WorkloadError::UnknownRestApiError),
        }
    }

    fn description(&self) -> &str {
        match *self {
            WorkloadError::HttpError(ref err) => err.description(),
            WorkloadError::Utf8Error(ref err) => err.description(),
            WorkloadError::UriError(ref err) => err.description(),
            WorkloadError::IoError(ref err) => err.description(),
            WorkloadError::JsonError(ref err) => err.description(),
            WorkloadError::ProtobufError(ref err) => err.description(),
            WorkloadError::BatchReadingError(ref err) => err.description(),
            WorkloadError::NoBatchError => "There was an error resulting in lacking a batch to submit.",
            WorkloadError::UnknownRestApiError => "The rest api produced an error response that we were not expecting.",
        }
    }
}

impl From<BatchReadingError> for WorkloadError {
    fn from(err: BatchReadingError) -> Self {
        WorkloadError::BatchReadingError(err)
    }
}

impl From<io::Error> for WorkloadError {
    fn from(err: io::Error) -> Self {
        WorkloadError::IoError(err)
    }
}

impl From<protobuf::ProtobufError> for WorkloadError {
    fn from(err: protobuf::ProtobufError) -> Self {
        WorkloadError::ProtobufError(err)
    }
}

impl From<HyperError> for WorkloadError {
    fn from(err: HyperError) -> Self {
        WorkloadError::HttpError(err)
    }
}

impl From<Utf8Error> for WorkloadError {
    fn from(err: Utf8Error) -> Self {
        WorkloadError::Utf8Error(err)
    }
}

impl From<UriError> for WorkloadError {
    fn from(err: UriError) -> Self {
        WorkloadError::UriError(err)
    }
}

impl From<serde_json::Error> for WorkloadError {
    fn from(err: serde_json::Error) -> Self {
        WorkloadError::JsonError(err)
    }
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
            BatchReadingError::MessageError(ref err) =>
                write!(f, "Error occurred reading messages: {}", err),
            BatchReadingError::BatchingError(ref err) =>
                write!(f, "Error creating the batch: {}", err),
            BatchReadingError::UnknownError =>
                write!(f, "There was an unknown batching error."),
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
        BatchListFeeder {
            batch_source,
        }
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

        if batches.len() == 0 {
            return None;
        }

        /// Construct a BatchList out of the read batches
        let mut batch_list = BatchList::new();
        batch_list.set_batches(protobuf::RepeatedField::from_vec(batches));

        Some(Ok(batch_list))
    }
}

pub struct InfiniteBatchListIterator<'a> {
    batches : &'a mut Iterator<Item = BatchResult>,
}

impl<'a> InfiniteBatchListIterator<'a> {
    pub fn new(batches: &'a mut Iterator<Item = BatchResult>) -> Self {
        InfiniteBatchListIterator {
            batches: batches,
        }
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

        let batches = vec!(batch);
        let mut batch_list = BatchList::new();
        batch_list.set_batches(protobuf::RepeatedField::from_vec(batches));
        Some(Ok(batch_list))
    }
}
