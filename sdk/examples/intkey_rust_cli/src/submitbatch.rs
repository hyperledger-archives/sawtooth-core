use hyper;
use hyper::Method;
use hyper::client::{Client, Request};
use hyper::header::{ContentLength, ContentType};
use futures::{future, Future};
use futures::Stream;
use tokio_core;

use sawtooth_sdk::messages::batch::BatchList;

use errors::IntkeyError;
use protobuf::Message;



pub fn submit_batch_list(url: Option<&str>, batch_list: &BatchList) -> Result<(), IntkeyError> {
    let url = match url {
        Some(v) => String::from(v) + "/batches",
        None => String::from("http://127.0.0.1:8008/batches")
    };

    let hyper_uri = match url.parse::<hyper::Uri>() {
        Ok(uri) => uri,
        Err(e) => return Err(IntkeyError::SubmissionError {
            error_details: (format!("Invalid URL: {}: {}", e, url))
        }),
    };

    match hyper_uri.scheme() {
        Some(scheme) => {
            if scheme != "http" {
                return Err(IntkeyError::SubmissionError {
                    error_details: (format!(
                    "Unsupported scheme ({}) in URL: {}",
                    scheme, url
                ))
                });
            }
        }
        None => {
            return Err(IntkeyError::SubmissionError {
                error_details: (format!("No scheme in URL: {}", url))
            });
        }
    }

    let mut core = tokio_core::reactor::Core::new()?;
    let handle = core.handle();
    let client = Client::configure().build(&handle);

    let bytes = batch_list.write_to_bytes()?;

    let mut req = Request::new(Method::Post, hyper_uri);
    req.headers_mut().set(ContentType::octet_stream());
    req.headers_mut().set(ContentLength(bytes.len() as u64));
    req.set_body(bytes);

    let work = client.request(req).and_then(|res| {
        res.body()
            .fold(Vec::new(), |mut v, chunk| {
                v.extend(&chunk[..]);
                future::ok::<_, hyper::Error>(v)
            })
            .and_then(move |chunks| {
                let body = String::from_utf8(chunks).unwrap();
                future::ok(body)
            })
    });

    core.run(work)?;

    Ok(())
}
