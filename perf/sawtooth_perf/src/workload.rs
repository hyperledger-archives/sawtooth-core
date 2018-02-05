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

use std::error;
use std::fmt;
use std::io;
use std::iter::Cycle;
use std::rc::Rc;
use std::str::FromStr;
use std::string::{FromUtf8Error, ParseError};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::time;
use std::vec::IntoIter;

use chrono;
use futures::{Future, Stream};
use futures::stream::Collect;
use hyper::Body;
use hyper::client::{Client, Request, Response, HttpConnector};
use hyper::Chunk;
use hyper::header::{Authorization, Basic, ContentType, ContentLength};
use hyper::Method;
use hyper::Error as HyperError;
use hyper::error::UriError;
use hyper::Uri;
use protobuf;
use protobuf::Message;
use serde_json;
use tokio_core::reactor::Handle;

use sawtooth_sdk::messages::batch::BatchList;

use batch_submit::BatchListResult;
use batch_submit::BatchReadingError;


#[derive(Debug)]
pub enum WorkloadError {
    HttpError(HyperError),
    Utf8Error(FromUtf8Error),
    UriError(UriError),
    JsonError(serde_json::Error),
    ProtobufError(protobuf::ProtobufError),
    ParseError(ParseError),
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
            WorkloadError::ParseError(ref err) => write!(f, "Error parsing str to String: {}", err),
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
            WorkloadError::ParseError(ref err) => err.cause(),
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
            WorkloadError::ParseError(ref err) => err.description(),
            WorkloadError::BatchReadingError(ref err) => err.description(),
            WorkloadError::NoBatchError => "There was an error resulting in lacking a batch to submit.",
            WorkloadError::UnknownRestApiError => "The rest api produced an error response that we were not expecting.",
        }
    }
}

impl From<ParseError> for WorkloadError {
    fn from(err: ParseError) -> Self {
        WorkloadError::ParseError(err)
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

impl From<FromUtf8Error> for WorkloadError {
    fn from(err: FromUtf8Error) -> Self {
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

/// Returned by the HTTP Post to /batches on the REST Api.
#[derive(Debug)]
#[derive(Deserialize)]
struct Link {
    link: String,
}

/// A BatchStatus for one batch; returned by the GET /batch_statuses route.
#[derive(Deserialize)]
struct BatchStatus {
    status: String,
}

/// The full response from GET /batch_statuses.
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

/// Counts sent, committed, invalid, and queue full for Batches and Batch Status responses
// from the Sawtooth REST Api.
pub struct HTTPRequestCounter {
    sent_count: AtomicUsize,
    committed_count: AtomicUsize,
    invalid_count: AtomicUsize,
    queue_full_count: AtomicUsize,
}

impl HTTPRequestCounter {

    pub fn new() -> Self {
        HTTPRequestCounter {
            sent_count: AtomicUsize::new(0),
            committed_count: AtomicUsize::new(0),
            invalid_count: AtomicUsize::new(0),
            queue_full_count: AtomicUsize::new(0),
         }
     }

    pub fn increment_committed(&self) {
        self.committed_count.fetch_add(1, Ordering::Relaxed);
    }

    pub fn increment_sent(&self) {
        self.sent_count.fetch_add(1, Ordering::Relaxed);
    }

    pub fn increment_invalid(&self) {
        self.invalid_count.fetch_add(1, Ordering::Relaxed);
    }

    pub fn increment_queue_full(&self) {
        self.queue_full_count.fetch_add(1, Ordering::Relaxed);
    }

    pub fn log(&self, seconds: u64, nanoseconds: u32) {
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

/// Log if time since last log is greater than update time.
pub fn log(counter: Rc<HTTPRequestCounter>,
       last_log_time: &mut time::Instant,
       update_time: u32) -> Result<(), WorkloadError>
{
    let log_time = time::Instant::now() - *last_log_time;
    if log_time.as_secs() as u32 >= update_time {
        counter.log(log_time.as_secs(), log_time.subsec_nanos());
        *last_log_time = time::Instant::now();
    }
    Ok(())
}

/// Call next on the BatchList Iterator and return the batchlist if no error.
pub fn get_next_batchlist(batch_list_iter: &mut Iterator<Item = BatchListResult>)
    -> Result<BatchList, WorkloadError>
{
    match batch_list_iter.next() {
        Some(Ok(batch_list)) => Ok(batch_list),
        Some(Err(err)) => return Err(WorkloadError::from(err)),
        None => return Err(WorkloadError::NoBatchError),
    }
}

/// Create the request from the next Target Url and the batchlist.
pub fn form_request_from_batchlist(targets: &mut Cycle<IntoIter<String>>,
                                   batch_list: Result<BatchList, WorkloadError>,
                                   basic_auth: Option<String>)
    -> Result<Request, WorkloadError>
{
    let mut batch_url = targets.next().unwrap();
    batch_url.push_str("/batches");
    debug!("Batches POST: {}", batch_url);

    let bytes = batch_list?.write_to_bytes()?;
    let mut req = Request::new(Method::Post, Uri::from_str(&batch_url)?);
    let content_len = bytes.len() as u64;
    req.set_body(bytes);
    req.headers_mut().set(ContentType::octet_stream());
    req.headers_mut().set(ContentLength(content_len));

    match basic_auth {
        Some(ref basic_auth) => {
            req.headers_mut().set(
                Authorization(
                    Basic::from_str(&basic_auth)?
                )
            );
        },
        None => {},
    }

    Ok(req)
}

/// Log if there is a HTTP Error.
fn handle_http_error(response: Result<Response, HyperError>)
    -> Result<Response, HyperError>
{
    match response {
        Ok(response) => Ok(response),
        Err(err) => {
            info!("{}", err);
            Err(err)
        },
    }
}

/// Collect the response body into a Vec<Chunk>.
fn resolve_future_response_body(response: Response)
    -> Collect<Body>
{
    response.body().collect()
}

/// Create a string out of the bytes in the Chunks.
fn collect_future_bytes_to_string(chunks: Vec<Chunk>)
    -> Result<String, WorkloadError>
{
    let bytes = chunks.iter().fold(vec!(), |mut v, ref c| {
        v.append(&mut c.to_vec());
        v
    });
    Ok(String::from_utf8(bytes)?)
}

/// Group the /batches POST and the /batch_status GET together.
pub fn make_request(client: Rc<Client<HttpConnector>>,
                handle: Handle,
                counter: Rc<HTTPRequestCounter>,
                req: Result<Request, WorkloadError>,
                basic_auth: Option<String>) -> Result<(), WorkloadError>
{
    let handle_clone = handle.clone();
    let counter_c = Rc::clone(&counter);
    match req {
        Ok(req) => {
            counter.increment_sent();
            let response_future = client.request(req)
                .then(|response: Result<Response, HyperError>| {
                    handle_http_error(response)
                })
                .and_then(|response:Response| {
                    resolve_future_response_body(response)
                })
                .map(|chunks: Vec<Chunk>| {
                    collect_future_bytes_to_string(chunks)
                })
                .map(move |json_string: Result<String, WorkloadError>| {
                    let counter_clone = Rc::clone(&counter_c);
                    handle_future_post_response(counter_clone, json_string)
                })
                .map(|uri: Result<Uri, WorkloadError>| {
                    form_request_from_batches_response(basic_auth, uri)
                }).map_err(|_| ())
                .and_then(move |req: Result<Request, WorkloadError>| {
                    let counter_clone = Rc::clone(&counter);
                    handle_getting_batch_status(client, handle, counter_clone, req)
                });

            Ok(handle_clone.spawn(response_future))
        },

        Err(err) => Err(err),
    }
}

/// Turn the POST /batches response String into an object, interpreting the String as JSON.
fn handle_future_post_response(counter: Rc<HTTPRequestCounter>,
                               string_json: Result<String, WorkloadError>)
    -> Result<Uri, WorkloadError>
{
    match string_json {
        Ok(s) => {
            let link = serde_json::from_str::<Link>(&s);
            match link {
                Ok(link) => {
                    let l = link.link;
                    let uri = Uri::from_str(l.as_ref())?;
                    Ok(uri)
                },
                Err(_) => {
                    let rest_api_error = serde_json::from_str::<RestApiErrorResponse>(&s)?;
                    if rest_api_error.error.code == 31 {
                        counter.increment_queue_full();
                    }
                    handle_rest_api_errors("Batch Status GET", rest_api_error);
                    Err(WorkloadError::UnknownRestApiError)
                }
            }

        },
        Err(err) => {
            debug!("Failed to decode bytes as Utf-8: {}", err);
            Err(WorkloadError::from(err))
        },
    }
}

/// Form a request from the Uri produced from the POST /batches response.
fn form_request_from_batches_response(basic_auth: Option<String>, uri: Result<Uri, WorkloadError>)
    -> Result<Request, WorkloadError>
{
    match uri {
        Ok(uri) => {
            let mut req: Request<Body> = Request::new(Method::Get, uri);
            match basic_auth {
                Some(ref basic_auth) => {
                    req.headers_mut().set(
                        Authorization(
                            Basic::from_str(&basic_auth)?
                        )
                    );
                    Ok(req)
                },
                None => {
                    Ok(req)
                },
            }
        },
        Err(err) => {
            debug!("{}", err);
            Err(WorkloadError::from(err))
        }
    }
}


/// Group the steps for the /batch_status GET together.
fn handle_getting_batch_status(client: Rc<Client<HttpConnector>>,
                               handle: Handle,
                               counter: Rc<HTTPRequestCounter>,
                               req: Result<Request, WorkloadError>)
    -> Result<(), ()>
{
    match req {
        Ok(req) => {
            let client_get = client.request(req)
                .then(|response: Result<Response, HyperError>| {
                    handle_http_error(response)
                })
                .and_then(|response: Response| {
                    resolve_future_response_body(response)
                })
                .map(|chunks: Vec<Chunk>| {
                    collect_future_bytes_to_string(chunks)
                })
                .map(|json_string: Result<String, WorkloadError>| {
                    get_future_batch_status_response_json(json_string)
                })
                .map(|batch_statuses_response: Option<BatchStatusesResponse>| {
                    increment_committed_or_invalid(counter, batch_statuses_response)
                });
            drop(client);
            Ok(handle.spawn(client_get.map_err(|_| ())))
        },
        Err(err) => {
            debug!("{}", err);
            Ok(())
        },
    }
}

/// Turn the String from the /batch_status GET into an object, interpreting the String as JSON.
fn get_future_batch_status_response_json(json_string: Result<String, WorkloadError>)
    -> Option<BatchStatusesResponse>
{
    match json_string {
        Ok(s) => {
            match serde_json::from_str::<BatchStatusesResponse>(&s) {
                Ok(batch_statuses) => Some(batch_statuses),
                Err(_) => {
                    match serde_json::from_str::<RestApiErrorResponse>(&s) {
                        Ok(rest_api_error) => {
                            handle_rest_api_errors("Batches POST", rest_api_error);
                        },
                        Err(_) => info!(
                            "The rest api responded with json that is
                            neither a batch response or error response."),
                    }
                    None
                },
            }
        },
        Err(err) => {
            debug!("Failed to decode bytes as Utf-8: {}", err);
            None
        },
    }
}

/// If a non-error response comes back from the Sawtooth REST Api, increment the counter
/// based on committed or invalid response.
fn increment_committed_or_invalid(counter: Rc<HTTPRequestCounter>,
                                  batch_statuses_response: Option<BatchStatusesResponse>)
    -> ()
{
    match batch_statuses_response {
        Some(response) => {
            match response.data.get(0) {
                Some(batch_status) => {
                    if batch_status.status == "COMMITTED" {
                        counter.increment_committed();
                    } else if batch_status.status == "INVALID" {
                        counter.increment_invalid();
                    }
                },
                None => {},
            }
        },
        None => {},
    }
}

fn handle_rest_api_errors(submit: &str, rest_api_error: RestApiErrorResponse) {

    let e = rest_api_error.error;
    info!("{}: {}: {}: {}", submit, e.code, e.title, e.message);
}
