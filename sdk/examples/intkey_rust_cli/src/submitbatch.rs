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

const DEFAULT_URL: &'static str = "http://127.0.0.1:8008";
const BATCHES_ROUTE: &'static str = "/batches";


pub fn parse_batch_url(url: Option<&str>) -> String {
    match url {
        Some(v) => format!("{}{}", v, BATCHES_ROUTE),
        None => format!("{}{}", DEFAULT_URL, BATCHES_ROUTE),
    }

}


pub fn submit_batch_list(_url: Option<&str>, _batch_list: &BatchList) -> Result<(), IntkeyError> {

    let batch_url_string: String = parse_batch_url(_url);

    let hyper_uri = match batch_url_string.parse::<hyper::Uri>() {
        Ok(uri) => uri,
        Err(e) => return Err(IntkeyError::SubmissionError {
            error_details: (format!("Invalid URL: {}: {}", e, batch_url_string))
        }),
    };

    match hyper_uri.scheme() {
        Some(scheme) => {
            if scheme != "http" {
                return Err(IntkeyError::SubmissionError {
                    error_details: (format!(
                    "Unsupported scheme ({}) in URL: {}",
                    scheme, batch_url_string
                ))
                });
            }
        }
        None => {
            return Err(IntkeyError::SubmissionError {
                error_details: (format!("No scheme in URL: {}", batch_url_string))
            });
        }
    }

    let mut core = tokio_core::reactor::Core::new()?;
    let handle = core.handle();
    let client = Client::configure().build(&handle);

    let bytes = _batch_list.write_to_bytes()?;

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

#[cfg(test)]
mod batch_route_parsing {
    use super::{ parse_batch_url, DEFAULT_URL };

    #[test]
    fn test_batch_url_parsing() {
        let target_local = format!("http://127.0.0.1:8008/batches");
        let target_nonlocal = format!("http://233.209.153.26:3030/batches");

        let candidate_local = parse_batch_url(Some(DEFAULT_URL));
        let candidate_nonlocal = parse_batch_url(Some("http://233.209.153.26:3030"));

        assert_eq!(candidate_local, target_local);
        assert_eq!(candidate_nonlocal, target_nonlocal);

    }


}
