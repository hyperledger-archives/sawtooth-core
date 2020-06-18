// Copyright 2018 Bitwise IO, Inc.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

use base64::decode;
use dirs::home_dir;
use failure::Error;
use game::{Action, Game};
use reqwest::{Client, Url};
use sawtooth_sdk::signing::secp256k1::Secp256k1PrivateKey;
use sawtooth_sdk::signing::{create_context, PrivateKey, Signer};
use serde_json::{from_slice, to_vec, Value};
use std::collections::HashMap;
use std::fs::File;
use std::io::Read;
use std::path::PathBuf;
use std::thread::sleep;
use std::time::Duration;
use transaction_builder::TransactionBuilder;

#[derive(Deserialize, Debug)]
enum TransactionState {
    COMMITTED,
    INVALID,
    PENDING,
    UNKNOWN,
}

#[derive(Deserialize, Debug)]
struct InvalidTransaction {
    id: String,
    message: String,
}

#[derive(Deserialize, Debug)]
struct TransactionData {
    id: String,
    invalid_transactions: Vec<InvalidTransaction>,
    status: TransactionState,
}

#[derive(Deserialize, Debug)]
struct TransactionStatus {
    data: Vec<TransactionData>,
    link: String,
}

/// Client for the Battleship transaction family
///
/// Handles talking to the REST API
pub struct BattleshipClient<'a> {
    url: String,
    key: Box<dyn PrivateKey>,
    client: Client,
    builder: TransactionBuilder<'a>,
}

fn get_key_dir() -> Option<PathBuf> {
    let home = home_dir()?;

    Some([home.to_str()?, ".sawtooth", "keys"].iter().collect())
}

impl<'a> BattleshipClient<'a> {
    /// Creates a new client by loading the given key from disk
    pub fn new<S: Into<String>>(url: S, key: S) -> Result<BattleshipClient<'a>, Error> {
        let mut key_path = get_key_dir().ok_or_else(|| format_err!("ASDF"))?;
        key_path.push(key.into());
        let pem = key_path.with_extension("priv");

        let key = {
            let mut file = File::open(pem.as_path().to_str().ok_or_else(|| format_err!("ASDF"))?)?;
            let mut contents = String::new();
            file.read_to_string(&mut contents)?;
            Box::new(
                Secp256k1PrivateKey::from_hex(&contents.trim())
                    .map_err(|e| format_err!("{}", e))?,
            )
        };

        Ok(BattleshipClient {
            url: url.into(),
            key,
            client: Client::new(),
            builder: Self::generate_builder(),
        })
    }

    /// Creates a new client with the given in-memory key
    pub fn new_with_key<S: Into<String>>(
        url: S,
        key: Box<dyn PrivateKey>,
    ) -> Result<BattleshipClient<'a>, Error> {
        Ok(BattleshipClient {
            url: url.into(),
            key,
            client: Client::new(),
            builder: Self::generate_builder(),
        })
    }

    fn generate_builder() -> TransactionBuilder<'a> {
        TransactionBuilder::new()
            .family_name("battleship")
            .family_version("1.0")
            .inputs(vec!["6e10df"])
            .outputs(vec!["6e10df"])
    }

    pub fn pub_key(&self) -> Result<String, Error> {
        let context = create_context("secp256k1").map_err(|e| format_err!("{}", e))?;

        Ok(context
            .get_public_key(&*self.key)
            .map_err(|e| format_err!("{}", e))?
            .as_hex())
    }

    fn get_path(&self, path: &str) -> Result<String, Error> {
        Ok(Url::parse(&self.url)?.join(path)?.as_str().to_owned())
    }

    fn send_action(&self, action: &Action) -> Result<String, Error> {
        let context = create_context("secp256k1").map_err(|e| format_err!("{}", e))?;
        let signer = Signer::new(&*context, &*self.key);

        let request_bytes = self
            .builder
            .clone()
            .payload(to_vec(&action)?)
            .signer(&signer)
            .build_request_bytes()?;

        let response: Value = self
            .client
            .post(&(self.url.clone() + "batches"))
            .body(request_bytes)
            .header(
                reqwest::header::CONTENT_TYPE,
                reqwest::header::HeaderValue::from_static("application/octet-stream"),
            )
            .send()?
            .json()?;

        Ok(response["link"]
            .as_str()
            .ok_or_else(|| format_err!("ASDF"))?
            .into())
    }

    /// Creates a game
    pub fn create(&self, name: &str, ships: Vec<String>) -> Result<String, Error> {
        self.send_action(&Action::Create {
            name: name.into(),
            ships,
        })
    }

    /// Joins a game
    pub fn join(&self, name: &str, board: Vec<Vec<String>>) -> Result<String, Error> {
        self.send_action(&Action::Join {
            name: name.into(),
            board,
        })
    }

    /// Fires on a space in a game
    pub fn fire(
        &self,
        name: &str,
        row: &str,
        col: &str,
        reveal_space: Option<char>,
        reveal_nonce: Option<String>,
    ) -> Result<String, Error> {
        self.send_action(&Action::Fire {
            name: name.into(),
            row: row.into(),
            column: col.into(),
            reveal_space,
            reveal_nonce,
        })
    }

    /// Lists games
    pub fn list(&self) -> Result<HashMap<String, Game>, Error> {
        let response: Value = self
            .client
            .get(&self.get_path("/state?address=6e10df")?)
            .send()?
            .json()?;

        Ok(response["data"]
            .as_array()
            .unwrap()
            .iter()
            .map(|json| {
                let entry: HashMap<String, Game> =
                    from_slice(&decode(json["data"].as_str().unwrap()).unwrap()).unwrap();
                let key = entry.keys().next().unwrap();
                (key.clone(), entry[key].clone())
            })
            .collect())
    }

    /// Gets a particular game from the list
    pub fn get_game(&self, name: &str) -> Result<Game, Error> {
        let games = self.list()?;

        Ok(games
            .get(name)
            .ok_or_else(|| format_err!("Game `{}` not found!", name))?
            .clone())
    }

    /// Waits for transaction to complete
    ///
    /// Expects a transaction link such as those returned by `BattleshipClient.create`
    pub fn wait(&self, link: &str, wait: u64) -> Result<(), Error> {
        for _ in 0..wait {
            let response: TransactionStatus = self.client.get(link).send()?.json()?;

            match response.data[0].status {
                TransactionState::COMMITTED => return Ok(()),
                TransactionState::INVALID => Err(format_err!(
                    "Invalid transaction: {}",
                    response.data[0].invalid_transactions[0].message
                ))?,
                TransactionState::PENDING => sleep(Duration::new(1, 0)),
                TransactionState::UNKNOWN => sleep(Duration::new(1, 0)),
            }
        }

        Err(format_err!("Waited too long for transaction to complete!"))
    }
}
