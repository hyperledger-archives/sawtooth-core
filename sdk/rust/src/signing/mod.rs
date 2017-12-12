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

mod pem_loader;
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

pub trait Context {
    fn get_algorithm_name(&self) -> &str;
    fn sign(&self, message: &[u8], key: &PrivateKey) -> Result<String, Error>;
    fn verify(&self, signature: &str, message: &[u8], key: &PublicKey) -> Result<bool, Error>;
    fn get_public_key(&self, private_key: &PrivateKey) -> Result<Box<PublicKey>, Error>;
}

pub fn create_context(algorithm_name: &str) -> Result<Box<Context>, Error> {
    match algorithm_name {
        "secp256k1" => Ok(Box::new(secp256k1::Secp256k1Context::new())),
        _ => Err(Error::NoSuchAlgorithm(format!("no such algorithm: {}", algorithm_name)))
    }
}

pub struct CryptoFactory<'a> {
    context: &'a Context
}

impl<'a> CryptoFactory<'a> {
    pub fn new(context: &'a Context) -> Self {
        CryptoFactory{ context: context }
    }

    pub fn get_context(&self) -> &Context {
        return self.context
    }

    pub fn new_signer(&self, key: &'a PrivateKey) -> Signer {
        Signer::new(self.context, key)
    }
}

pub struct Signer<'a> {
    context: &'a Context,
    key: &'a PrivateKey
}

impl<'a> Signer<'a> {
    pub fn new(context: &'a Context, key: &'a PrivateKey) -> Self {
        Signer {
            context: context,
            key: key
        }
    }

    pub fn sign(&self, message: &[u8]) -> Result<String, Error> {
        self.context.sign(message, self.key)
    }
}

#[cfg(test)]
mod signing_test {
    use super::create_context;

    #[test]
    fn no_such_algorithm() {
        let result = create_context("invalid");
        assert!(result.is_err())
    }
}
