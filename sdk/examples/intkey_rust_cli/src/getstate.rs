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

pub fn get_state(_url: Option<&str>, _key_name: Option<&str>) -> Result<(), IntkeyError> {


    let key_address = match _key_name {
        Some(v) => storage_addr_from_name(v),
        None => String::from(""),
    };

    let get_url = match _url {
        Some(v) => format!("{}{}{}", v, "/state?address=1cf126", key_address),
        None => format!("http://127.0.0.1:8008/state?address=1cf126{}", key_address),
    };



    //
    let hyper_uri = match get_url.parse::<hyper::Uri>() {
        Ok(uri) => uri,
        Err(e) => return Err(IntkeyError::SubmissionError{ error_details: (format!("Invalid get URL: {}: {}", e, get_url)) }),
    };
    //

    match hyper_uri.scheme() {
        Some(scheme) => {
            if scheme != "http" {
                return Err(IntkeyError::SubmissionError{
                    error_details: (format!(
                    "Unsupported scheme ({}) in URL: {}",
                    scheme, get_url
                ))
                });
            }
        }
        None => {
            return Err(IntkeyError::SubmissionError {
                error_details: (format!("No scheme in URL: {}", get_url))
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

