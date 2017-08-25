pub mod secp256k1;

use std::error::Error as StdError;
use std;
use std::borrow::Borrow;

#[derive(Debug)]
pub enum Error {
    NoSuchAlgorithm(String),
    ParseError(String),
    SigningError(Box<StdError>)
}

impl StdError for Error {
    fn description(&self) -> &str {
        match *self {
            Error::NoSuchAlgorithm(ref msg) => msg,
            Error::ParseError(ref msg) => msg,
            Error::SigningError(ref err) => err.description()
        }
    }

    fn cause(&self) -> Option<&StdError> {
        match *self {
            Error::NoSuchAlgorithm(_) => None,
            Error::ParseError(_) => None,
            Error::SigningError(ref err) => Some(err.borrow())
        }
    }
}

impl std::fmt::Display for Error {
    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
        match *self {
            Error::NoSuchAlgorithm(ref s) =>
                write!(f, "NoSuchAlgorithm: {}", s),
            Error::ParseError(ref s) =>
                write!(f, "ParseError: {}", s),
            Error::SigningError(ref err) =>
                write!(f, "SigningError: {}", err.description())
        }
    }
}

pub trait PrivateKey {
    fn get_algorithm_name(&self) -> &str;
    fn as_hex(&self) -> String;
    fn as_slice(&self) -> &[u8];
}

pub trait PublicKey {
    fn get_algorithm_name(&self) -> &str;
    fn as_hex(&self) -> String;
    fn as_slice(&self) -> &[u8];
}

pub trait Algorithm {
    fn get_name(&self) -> &str;
    fn sign(&self, message: &[u8], key: &PrivateKey) -> Result<String, Error>;
    fn verify(&self, signature: &str, message: &[u8], key: &PublicKey) -> Result<bool, Error>;
    fn get_public_key(&self, private_key: &PrivateKey) -> Result<Box<PublicKey>, Error>;
}

pub fn create_algorithm(name: &str) -> Result<Box<Algorithm>, Error> {
    match name {
        "secp256k1" => Ok(Box::new(secp256k1::Secp256k1Algorithm::new())),
        _ => Err(Error::NoSuchAlgorithm(format!("no such algorithm: {}", name)))
    }
}

pub struct CryptoFactory<'a> {
    algorithm: &'a Algorithm
}

impl<'a> CryptoFactory<'a> {
    pub fn new(algorithm: &'a Algorithm) -> Self {
        CryptoFactory{ algorithm: algorithm }
    }

    pub fn get_algorithm(&self) -> &Algorithm {
        return self.algorithm
    }

    pub fn new_signer(&self, key: &'a PrivateKey) -> Signer {
        Signer::new(self.algorithm, key)
    }
}

pub struct Signer<'a> {
    algorithm: &'a Algorithm,
    key: &'a PrivateKey
}

impl<'a> Signer<'a> {
    pub fn new(algorithm: &'a Algorithm, key: &'a PrivateKey) -> Self {
        Signer {
            algorithm: algorithm,
            key: key
        }
    }

    pub fn sign(&self, message: &[u8]) -> Result<String, Error> {
        self.algorithm.sign(message, self.key)
    }
}

#[cfg(test)]
mod signing_test {
    use super::create_algorithm;

    #[test]
    fn no_such_algorithm() {
        let result = create_algorithm("invalid");
        assert!(result.is_err())
    }
}
