use std;
use std::num::ParseIntError;
use base64::DecodeError;
use serde_cbor;
use serde_json;
use sawtooth_sdk::signing;
use protobuf;
use hyper;


impl From<std::option::NoneError> for IntkeyError {
    fn from(_err: std::option::NoneError) -> Self {
        IntkeyError::ParsedNoneError
    }
}

impl From<std::io::Error> for IntkeyError {
    fn from(_err: std::io::Error) -> Self {
        IntkeyError::IoError
    }
}

impl From<signing::Error> for IntkeyError {
    fn from(_err: signing::Error) -> Self {
        IntkeyError::SawtoothSigningError
    }
}

impl From<protobuf::ProtobufError> for IntkeyError {
    fn from(_err: protobuf::ProtobufError) -> Self {
        IntkeyError::ProtocolBufferError
    }
}

impl From<hyper::Error> for IntkeyError {
    fn from(_err: hyper::Error) -> Self {
        IntkeyError::HyperError
    }
}

impl From<DecodeError> for IntkeyError {
    fn from(_err: DecodeError) -> Self {
        IntkeyError::Base64DecodeError
    }
}

impl From<serde_cbor::error::Error> for IntkeyError {
    fn from(_err: serde_cbor::error::Error) -> Self {
        IntkeyError::SerdeCborError
    }
}

impl From<serde_json::Error> for IntkeyError {
    fn from(_err: serde_json::Error) -> Self {
        IntkeyError::SerdeJsonError
    }
}

impl From<std::num::ParseIntError> for IntkeyError {
    fn from(_err: ParseIntError) -> Self {
        IntkeyError::ParseIntError
    }
}


#[derive(Fail, Debug)]
pub enum IntkeyError {

    #[fail(display = "Failed parsing invalid integer value. Expected 32 bit integer")]
    ParseIntError, 

    #[fail(display = "For safety reasons, only ASCII characters are allowed in key names.")]
    NonAsciiNameError,

    #[fail(display = "Verb must be either 'set', 'inc', or 'dec'. Got {}", received_verb)]
    BadVerb {
        received_verb: String
    },

    #[fail(display = "Desired value is too large. Max value is 4,294,967,295")]
    ValueOverflow,

    #[fail(display = "Max key name length is 20 characters. Got key of {} char length", key_length)]
    NameOverflow {
        key_length: usize
    },

    #[fail(display = "The CLI parser rejected one of your arguments (it probably contains non-ASCII \
                      code or special characters). Check the arguments you're \
                      passing to intkey, or type 'intkey_cli_bin --help for instructions")]
    ParsedNoneError,

    #[fail(display = "We were unable to determine your username from environment\
                      variables, and therefore could not load your signing keys.")]
    UsernameError,

    #[fail(display = "Unable to locate key files with which to sign transaction")]
    KeyfileError,

    #[fail(display = "Found an empty private key file; unable to sign transactions")]
    EmptyKeyfileError,

    #[fail(display = "Something went wrong when loading your private key. Check\
                      That your keyfile exists, is not empty, and that your\
                      environment variables are set correctly")]
    IoError,

    #[fail(display = "Something went wrong with sawtooth's signing procedure")]
    SawtoothSigningError,

    #[fail(display = "Error in serializing batch to protocol buffer")]
    ProtocolBufferError,

    #[fail(display = "Error submitting batch; network request failed. Details: {}", error_details)]
    SubmissionError {
        error_details: String
    },

    #[fail(display = "Something failed with Hyper")]
    HyperError,

    #[fail(display = "There was an error decoding HTTP response from base64")]
    Base64DecodeError,

    #[fail(display = "Serde CBOR failed to decode the HTTP response from CBOR")]
    SerdeCborError,

    #[fail(display = "Serde JSON decoder failed")]
    SerdeJsonError,

    #[fail(display = "Sorry, the no matches found. The key(s) queried may not yet exist in the\
                      current state tree. Use the 'set' verb to create a new key value pair.")]
    NonexistentKeyError,
}