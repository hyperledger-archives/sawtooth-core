/*
 * Copyright 2018 Intel Corporation
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

/// Tools for interacting with the Sawtooth Rest API
use std::cell::RefCell;
use std::error;
use std::fmt;
use std::io;
use std::iter::Cycle;
use std::rc::Rc;
use std::str::FromStr;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::time;
use std::vec::IntoIter;

use chrono;
use futures::Future;
use hyper::client::{Client, HttpConnector, Request, Response};
use hyper::error::UriError;
use hyper::header::{Authorization, Basic, ContentLength, ContentType};
use hyper::Error as HyperError;
use hyper::Method;
use hyper::StatusCode;
use hyper::Uri;
use protobuf;
use protobuf::Message;
use tokio_core::reactor::Handle;

use sawtooth_sdk::messages::batch::BatchList;

use batch_submit::BatchListResult;
use batch_submit::BatchReadingError;

use batch_map::BatchMap;

#[derive(Debug)]
pub enum WorkloadError {
    HttpError(HyperError),
    UriError(UriError),
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
            WorkloadError::UriError(ref err) => write!(f, "A uri error occurred: {}", err),
            WorkloadError::IoError(ref err) => write!(f, "An io error occurred: {}", err),
            WorkloadError::ProtobufError(ref err) => {
                write!(f, "A protobuf error occurred: {}", err)
            }
            WorkloadError::BatchReadingError(ref err) => {
                write!(f, "A generic batch reading error occurred: {}", err)
            }
            WorkloadError::NoBatchError => write!(
                f,
                "An unknown error occurred resulting in a lack of a batch to send"
            ),
            WorkloadError::UnknownRestApiError => write!(
                f,
                "This error produced a rest api error that should be handled."
            ),
        }
    }
}

impl error::Error for WorkloadError {
    fn cause(&self) -> Option<&error::Error> {
        match *self {
            WorkloadError::HttpError(ref err) => err.cause(),
            WorkloadError::UriError(ref err) => err.cause(),
            WorkloadError::IoError(ref err) => err.cause(),
            WorkloadError::ProtobufError(ref err) => err.cause(),
            WorkloadError::BatchReadingError(ref err) => err.cause(),
            WorkloadError::NoBatchError => Some(&WorkloadError::NoBatchError),
            WorkloadError::UnknownRestApiError => Some(&WorkloadError::UnknownRestApiError),
        }
    }

    fn description(&self) -> &str {
        match *self {
            WorkloadError::HttpError(ref err) => err.description(),
            WorkloadError::UriError(ref err) => err.description(),
            WorkloadError::IoError(ref err) => err.description(),
            WorkloadError::ProtobufError(ref err) => err.description(),
            WorkloadError::BatchReadingError(ref err) => err.description(),
            WorkloadError::NoBatchError => {
                "There was an error resulting in lacking a batch to submit."
            }
            WorkloadError::UnknownRestApiError => {
                "The rest api produced an error response that we were not expecting."
            }
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

impl From<UriError> for WorkloadError {
    fn from(err: UriError) -> Self {
        WorkloadError::UriError(err)
    }
}

/// Counts sent, committed, invalid, and queue full for Batches and Batch Status responses
// from the Sawtooth REST Api.
pub struct HTTPRequestCounter {
    sent_count: AtomicUsize,
    queue_full_count: AtomicUsize,
}

impl HTTPRequestCounter {
    pub fn new() -> Self {
        HTTPRequestCounter {
            sent_count: AtomicUsize::new(0),
            queue_full_count: AtomicUsize::new(0),
        }
    }

    pub fn increment_sent(&self) {
        self.sent_count.fetch_add(1, Ordering::Relaxed);
    }

    pub fn increment_queue_full(&self) {
        self.queue_full_count.fetch_add(1, Ordering::Relaxed);
    }

    pub fn log(&self, seconds: u64, nanoseconds: u32) {
        let update = seconds as f64 + f64::from(nanoseconds) * 1e-9;
        println!(
            "{}, Batches/s {:.3}",
            self,
            self.sent_count.load(Ordering::Relaxed) as f64 / update
        );

        self.sent_count.store(0, Ordering::Relaxed);
        self.queue_full_count.store(0, Ordering::Relaxed);
    }
}

impl fmt::Display for HTTPRequestCounter {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        let time = chrono::Utc::now();
        write!(
            f,
            "{0}, Sent: {1}, Queue Full {2}",
            time.format("%h-%d-%Y %H:%M:%S%.3f").to_string(),
            self.sent_count.load(Ordering::Relaxed),
            self.queue_full_count.load(Ordering::Relaxed)
        )
    }
}

/// Log if time since last log is greater than update time.
pub fn log(
    counter: &Rc<HTTPRequestCounter>,
    last_log_time: &mut time::Instant,
    update_time: u32,
) -> Result<(), WorkloadError> {
    let log_time = time::Instant::now() - *last_log_time;
    if log_time.as_secs() as u32 >= update_time {
        counter.log(log_time.as_secs(), log_time.subsec_nanos());
        *last_log_time = time::Instant::now();
    }
    Ok(())
}

/// Call next on the BatchList Iterator and return the batchlist if no error.
pub fn get_next_batchlist(
    batch_list_iter: &mut Iterator<Item = BatchListResult>,
    batch_map: &Rc<RefCell<BatchMap>>,
    batches: &Rc<RefCell<Vec<BatchList>>>,
) -> Result<BatchList, WorkloadError> {
    match batches.borrow_mut().pop() {
        Some(batchlist) => Ok(batchlist),
        None => match batch_list_iter.next() {
            Some(Ok(batch_list)) => {
                batch_map.borrow_mut().add(batch_list.clone());
                Ok(batch_list)
            }
            Some(Err(err)) => Err(WorkloadError::from(err)),
            None => Err(WorkloadError::NoBatchError),
        },
    }
}

/// Create the request from the next Target Url and the batchlist.
pub fn form_request_from_batchlist(
    targets: &mut Cycle<IntoIter<String>>,
    batch_list: Result<BatchList, WorkloadError>,
    basic_auth: &Option<String>,
) -> Result<(Request, Option<String>), WorkloadError> {
    let mut batch_url = targets.next().unwrap();
    batch_url.push_str("/batches");
    debug!("Batches POST: {}", batch_url);

    let batchlist_unwrapped = batch_list?;

    let batch_id = match batchlist_unwrapped.batches.last() {
        Some(batch) => Some(batch.header_signature.clone()),
        None => None,
    };
    let bytes = batchlist_unwrapped.write_to_bytes()?;
    let mut req = Request::new(Method::Post, Uri::from_str(&batch_url)?);
    let content_len = bytes.len() as u64;
    req.set_body(bytes);
    req.headers_mut().set(ContentType::octet_stream());
    req.headers_mut().set(ContentLength(content_len));

    if let Some(ref basic_auth) = *basic_auth {
        req.headers_mut()
            .set(Authorization(Basic::from_str(&basic_auth)?));
    }

    Ok((req, batch_id))
}

/// Log if there is a HTTP Error.
fn handle_http_error(
    response: Result<Response, HyperError>,
    batch_id: Option<String>,
    batches: &Rc<RefCell<Vec<BatchList>>>,
    batch_map: &Rc<RefCell<BatchMap>>,
    counter: &Rc<HTTPRequestCounter>,
) -> Result<(), HyperError> {
    if let Some(batch_id) = batch_id {
        match response {
            Ok(response) => match response.status() {
                StatusCode::Accepted => batch_map.borrow_mut().mark_submit_success(&batch_id),
                StatusCode::TooManyRequests => counter.increment_queue_full(),

                _ => if let Some(batchlist) =
                    batch_map.borrow_mut().get_batchlist_to_submit(&batch_id)
                {
                    batches.borrow_mut().push(batchlist)
                },
            },
            Err(err) => {
                if let Some(batchlist) = batch_map.borrow_mut().get_batchlist_to_submit(&batch_id) {
                    batches.borrow_mut().push(batchlist)
                }
                info!("{}", err);
            }
        }
    }
    Ok(())
}

/// POST the batchlist to the rest api.
pub fn make_request(
    client: &Rc<Client<HttpConnector>>,
    handle: &Handle,
    counter: Rc<HTTPRequestCounter>,
    batch_map: Rc<RefCell<BatchMap>>,
    batches: Rc<RefCell<Vec<BatchList>>>,
    req: Result<(Request, Option<String>), WorkloadError>,
) -> Result<(), WorkloadError> {
    let handle_clone = handle.clone();
    match req {
        Ok((req, batch_id)) => {
            counter.increment_sent();
            let response_future = client
                .request(req)
                .then(move |response: Result<Response, HyperError>| {
                    handle_http_error(response, batch_id, &batches, &batch_map, &counter)
                }).map(|_| ())
                .map_err(|_| ());

            handle_clone.spawn(response_future);

            Ok(())
        }

        Err(err) => Err(err),
    }
}
