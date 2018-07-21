use hyper;
use hyper::Method;
use hyper::client::{Client, Request};
use futures::{future, Future};
use futures::Stream;
use tokio_core;

use serde_json::{Value, Map, from_str };
use serde_cbor::{ from_slice };
use base64::{ decode };

use errors::IntkeyError;

use crypto::sha2::Sha512;
use crypto::digest::Digest;

const DEFAULT_URL: &'static str = "http://127.0.0.1:8008";
const INTKEY_NAMESPACE_PREFIX: &'static str = "1cf126";
const STATE_QUERY_ROUTE: &'static str = "/state?address=";

pub fn storage_addr_from_name(_name: &str) -> String {
    let mut sha = Sha512::new();
    let name_bytes = _name.as_bytes();
    sha.input(name_bytes);
    let result_string = sha.result_str();
    let hashed_name_bytes = result_string.as_bytes();
    let as_string = String::from_utf8_lossy(&hashed_name_bytes[64..]).into_owned();
    as_string
}


pub fn decode_and_format_response(x: &Value) -> Result<(), IntkeyError> {
    //Acts on individual key/value pairs.
    let base64_decoded = x.get(String::from("data"))?
                                           .as_str()?;
               
 
    let cbor_string = decode(base64_decoded)?;

    let kv_map: Map<String, Value> = from_slice(&cbor_string[0..])?;
    let mut key_iter = kv_map.keys();
    let key_name = key_iter.next()?;
    let value = kv_map.get(key_name)?
                      .as_u64()?;

    println!("  {} -> {}", key_name, value);
    Ok(())

}

pub fn req_url_as_string(_url: Option<&str>, _key_name: Option<&str>) -> String {
    let key_address = match _key_name {
        Some(v) => storage_addr_from_name(v),
        None => String::from(""),
    };

    match _url {
        Some(v) => format!("{}{}{}{}", v, STATE_QUERY_ROUTE, INTKEY_NAMESPACE_PREFIX, key_address),
        None => format!("{}{}{}{}", DEFAULT_URL, STATE_QUERY_ROUTE, INTKEY_NAMESPACE_PREFIX, key_address),
    }
}

pub fn get_state(_url: Option<&str>, _key_name: Option<&str>) -> Result<(), IntkeyError> {

    let req_url_string: String = req_url_as_string(_url, _key_name);

    let hyper_uri = match req_url_string.parse::<hyper::Uri>() {
        Ok(uri) => uri,
        Err(e) => return Err(IntkeyError::SubmissionError{ error_details: (format!("Invalid get URL: {}: {}", e, req_url_string)) }),
    };
    //

    match hyper_uri.scheme() {
        Some(scheme) => {
            if scheme != "http" {
                return Err(IntkeyError::SubmissionError{
                    error_details: (format!(
                    "Unsupported scheme ({}) in URL: {}",
                    scheme, req_url_string
                ))
                });
            }
        }
        None => {
            return Err(IntkeyError::SubmissionError {
                error_details: (format!("No scheme in URL: {}", req_url_string))
            });
        }
    }

    let mut core = tokio_core::reactor::Core::new()?;
    let handle = core.handle();
    let client = Client::configure().build(&handle);

    let req = Request::new(Method::Get, hyper_uri);
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

    let body = core.run(work)?;
    let response_as_serde_value: Value = from_str(&body)?;


    let mut data_vec_iter = response_as_serde_value.get(String::from("data"))?
                                                       .as_array()?
                                                       .iter();

    match data_vec_iter.len() {
        0 => return Err(IntkeyError::NonexistentKeyError),
        _ => data_vec_iter.try_for_each(|x| decode_and_format_response(x))?,
    }
    
    Ok(())
}


#[cfg(test)]
mod get_state_tests {
    use super::{ req_url_as_string, storage_addr_from_name, DEFAULT_URL };
    

    #[test]
    fn test_url_parsing_from_cli_args() {
        let nonlocal_ip = "http://233.209.153.26:3030";
        let test_key_address = storage_addr_from_name("testKey");
        let target_local_somekey = format!("http://127.0.0.1:8008/state?address=1cf126{}", test_key_address);
        let target_local_nonekey = format!("http://127.0.0.1:8008/state?address=1cf126{}", "");
        let target_nonlocal_somekey = format!("http://233.209.153.26:3030/state?address=1cf126{}", test_key_address);
        let target_nonlocal_nonekey = format!("http://233.209.153.26:3030/state?address=1cf126{}", "");

        let candidate_local_somekey = req_url_as_string(Some(DEFAULT_URL), Some("testKey"));
        let candidate_local_nonekey = req_url_as_string(Some(DEFAULT_URL), None);
        let candidate_nonlocal_somekey = req_url_as_string(Some(nonlocal_ip), Some("testKey"));
        let candidate_nonlocal_nonekey = req_url_as_string(Some(nonlocal_ip), None);

        assert_eq!(target_local_somekey, candidate_local_somekey);
        assert_eq!(target_local_nonekey, candidate_local_nonekey);
        assert_eq!(target_nonlocal_somekey, candidate_nonlocal_somekey);
        assert_eq!(target_nonlocal_nonekey, candidate_nonlocal_nonekey);
    }

}