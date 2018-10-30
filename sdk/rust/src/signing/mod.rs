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

pub mod secp256k1;

use std;
use std::borrow::Borrow;
use std::error::Error as StdError;

#[derive(Debug)]
pub enum Error {
    /// Returned when trying to create an algorithm which does not exist.
    NoSuchAlgorithm(String),
    /// Returned when an error occurs during deserialization of a Private or
    /// Public key from various formats.
    ParseError(String),
    /// Returned when an error occurs during the signing process.
    SigningError(Box<StdError>),
    /// Returned when an error occurs during key generation
    KeyGenError(String),
}

impl StdError for Error {
    fn description(&self) -> &str {
        match *self {
            Error::NoSuchAlgorithm(ref msg) => msg,
            Error::ParseError(ref msg) => msg,
            Error::SigningError(ref err) => err.description(),
            Error::KeyGenError(ref msg) => msg,
        }
    }

    fn cause(&self) -> Option<&StdError> {
        match *self {
            Error::NoSuchAlgorithm(_) => None,
            Error::ParseError(_) => None,
            Error::SigningError(ref err) => Some(err.borrow()),
            Error::KeyGenError(_) => None,
        }
    }
}

impl std::fmt::Display for Error {
    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
        match *self {
            Error::NoSuchAlgorithm(ref s) => write!(f, "NoSuchAlgorithm: {}", s),
            Error::ParseError(ref s) => write!(f, "ParseError: {}", s),
            Error::SigningError(ref err) => write!(f, "SigningError: {}", err.description()),
            Error::KeyGenError(ref s) => write!(f, "KeyGenError: {}", s),
        }
    }
}

/// A private key instance.
/// The underlying content is dependent on implementation.
pub trait PrivateKey {
    /// Returns the algorithm name used for this private key.
    fn get_algorithm_name(&self) -> &str;
    /// Return the private key encoded as a hex string.
    fn as_hex(&self) -> String;
    /// Return the private key bytes.
    fn as_slice(&self) -> &[u8];
}

/// A public key instance.
/// The underlying content is dependent on implementation.
pub trait PublicKey {
    /// Returns the algorithm name used for this public key.
    fn get_algorithm_name(&self) -> &str;
    /// Return the public key encoded as a hex string.
    fn as_hex(&self) -> String;
    /// Return the public key bytes.
    fn as_slice(&self) -> &[u8];
}

/// A context for a cryptographic signing algorithm.
pub trait Context {
    /// Returns the algorithm name.
    fn get_algorithm_name(&self) -> &str;
    /// Sign a message
    /// Given a private key for this algorithm, sign the given message bytes
    /// and return a hex-encoded string of the resulting signature.
    /// # Arguments
    ///
    /// * `message`- the message bytes
    /// * `private_key` the private key
    ///
    /// # Returns
    ///
    /// * `signature` - The signature in a hex-encoded string
    fn sign(&self, message: &[u8], key: &PrivateKey) -> Result<String, Error>;

    /// Verifies that the signature of a message was produced with the
    /// associated public key.
    /// # Arguments
    ///
    /// * `signature` - the hex-encoded signature
    /// * `message` - the message bytes
    /// * `public_key` - the public key to use for verification
    ///
    /// # Returns
    ///
    /// * `boolean` - True if the public key is associated with the signature for that method,
    ///            False otherwise
    fn verify(&self, signature: &str, message: &[u8], key: &PublicKey) -> Result<bool, Error>;

    /// Produce the public key for the given private key.
    /// # Arguments
    ///
    /// `private_key` - a private key
    ///
    /// # Returns
    /// * `public_key` - the public key for the given private key
    fn get_public_key(&self, private_key: &PrivateKey) -> Result<Box<PublicKey>, Error>;

    ///Generates a new random PrivateKey using this context.
    /// # Returns
    ///
    /// * `private_key` - a random private key
    fn new_random_private_key(&self) -> Result<Box<PrivateKey>, Error>;
}

pub fn create_context(algorithm_name: &str) -> Result<Box<Context>, Error> {
    match algorithm_name {
        "secp256k1" => Ok(Box::new(secp256k1::Secp256k1Context::new())),
        _ => Err(Error::NoSuchAlgorithm(format!(
            "no such algorithm: {}",
            algorithm_name
        ))),
    }
}
/// Factory for generating signers.
pub struct CryptoFactory<'a> {
    context: &'a Context,
}

impl<'a> CryptoFactory<'a> {
    /// Constructs a CryptoFactory.
    /// # Arguments
    ///
    /// * `context` - a cryptographic context
    pub fn new(context: &'a Context) -> Self {
        CryptoFactory { context }
    }

    /// Returns the context associated with this factory
    ///
    /// # Returns
    ///
    /// * `context` - a cryptographic context
    pub fn get_context(&self) -> &Context {
        self.context
    }

    /// Create a new signer for the given private key.
    ///
    /// # Arguments
    ///
    /// `private_key` - a private key
    ///
    /// # Returns
    ///
    /// * `signer` - a signer instance
    pub fn new_signer(&self, key: &'a PrivateKey) -> Signer {
        Signer::new(self.context, key)
    }
}

/// A convenient wrapper of Context and PrivateKey
pub struct Signer<'a> {
    context: &'a Context,
    key: &'a PrivateKey,
}

impl<'a> Signer<'a> {
    /// Constructs a new Signer
    ///
    /// # Arguments
    ///
    /// * `context` - a cryptographic context
    /// * `private_key` - private key
    pub fn new(context: &'a Context, key: &'a PrivateKey) -> Self {
        Signer { context, key }
    }

    /// Signs the given message.
    ///
    /// # Arguments
    ///
    /// * `message` - the message bytes
    ///
    /// # Returns
    ///
    /// * `signature` - the signature in a hex-encoded string
    pub fn sign(&self, message: &[u8]) -> Result<String, Error> {
        self.context.sign(message, self.key)
    }

    /// Return the public key for this Signer instance.
    ///
    /// # Returns
    ///
    /// * `public_key` - the public key instance
    pub fn get_public_key(&self) -> Result<Box<PublicKey>, Error> {
        self.context.get_public_key(self.key)
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
