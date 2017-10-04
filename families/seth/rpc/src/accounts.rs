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

use std::fmt::{Display, Formatter, Result as FmtResult};
use std::fs::File;
use std::io::Read;
use std::path::{PathBuf};
use std::error::Error as StdError;
use std::io::Error as IoError;
use sawtooth_sdk::signing::Error as SigningError;
use sawtooth_sdk::signing::secp256k1::{Secp256k1PrivateKey};
use sawtooth_sdk::signing::{PrivateKey, create_algorithm};
use client::{bytes_to_hex_str};
use rpassword;
use tiny_keccak;

#[derive(Clone)]
pub struct Account {
    alias: String,
    private_key: String,
    public_key: String,
    address: String,
}

#[derive(Debug)]
pub enum Error {
    IoError(IoError),
    ParseError(String),
    AliasNotFound,
    SigningError,
}

impl StdError for Error {
    fn description(&self) -> &str {
        match *self {
            Error::IoError(ref ie) => ie.description(),
            Error::ParseError(ref msg) => msg,
            Error::AliasNotFound => "Alias not found in data directory",
            Error::SigningError => "Signing failed",
        }
    }

    fn cause(&self) -> Option<&StdError> { None }
}

impl Display for Error {
    fn fmt(&self, f: &mut Formatter) -> FmtResult {
        match *self {
            Error::IoError(ref ie) => ie.fmt(f),
            Error::ParseError(ref msg) => write!(f, "ParseError: {}", msg),
            Error::AliasNotFound => write!(f, "AliasNotFound"),
            Error::SigningError => write!(f, "SigningError"),
        }
    }
}

impl From<IoError> for Error {
    fn from(e: IoError) -> Self {
        Error::IoError(e)
    }
}

impl From<SigningError> for Error {
    fn from(e: SigningError) -> Self {
        match e {
            SigningError::ParseError(msg) => Error::ParseError(msg),
            _ => Error::ParseError(String::from("Loading wif returned a non-parse error")),
        }
    }
}

fn get_data_dir() -> PathBuf {
    [&env!("HOME"), ".sawtooth"].iter().collect()
}

impl Account {
    pub fn load_from_alias(alias: &str) -> Result<Account, Error> {
        let mut key_path = get_data_dir();
        key_path.push(alias);
        let wif = key_path.with_extension("wif");
        let pem = key_path.with_extension("pem");

        let key = {
            if wif.as_path().is_file() {
                let key = Self::read_file(&wif)?;
                Secp256k1PrivateKey::from_wif(&key.trim())
            } else if pem.as_path().is_file() {
                let key = Self::read_file(&pem)?;
                if key.contains("ENCRYPTED") {
                    let prompt = format!("Enter Password to unlock {}:", alias);
                    let pass = rpassword::prompt_password_stdout(&prompt).unwrap();
                    Secp256k1PrivateKey::from_pem_with_password(&key.trim(), &pass)
                } else {
                    Secp256k1PrivateKey::from_pem(&key.trim())
                }
            } else {
                return Err(Error::AliasNotFound);
            }
        }?;

        let algorithm = create_algorithm("secp256k1").unwrap();
        let pub_key = algorithm.get_public_key(&key)?;

        Ok(Account{
            alias: String::from(alias),
            private_key: key.as_hex(),
            public_key: pub_key.as_hex(),
            address: pubkey_to_address(pub_key.as_slice()),
        })
    }

    fn read_file(keyfile: &PathBuf) -> Result<String, Error> {
        let mut file = File::open(keyfile.as_path().to_str().unwrap())?;
        let mut contents = String::new();
        file.read_to_string(&mut contents)?;
        Ok(contents)
    }

    pub fn sign(&self, message: &[u8]) -> Result<String, Error> {
        let algorithm = create_algorithm("secp256k1").unwrap();
        let key = Secp256k1PrivateKey::from_hex(&self.private_key).map_err(|_|
            Error::SigningError)?;
        algorithm.sign(message, &key).map_err(|_| Error::SigningError)
    }

    pub fn alias(&self) -> &str {
        &self.alias
    }

    pub fn address(&self) -> &str {
        &self.address
    }

    pub fn pubkey(&self) -> &str {
        &self.public_key
    }
}

pub fn pubkey_to_address(pub_key: &[u8]) -> String {
    bytes_to_hex_str(&tiny_keccak::keccak256(pub_key)[..20])
}
