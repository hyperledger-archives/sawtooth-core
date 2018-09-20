/*
 * Copyright 2018 Intel Corporation
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
use std;

use protobuf;

use sawtooth_sdk::messages;

#[derive(Debug)]
pub enum Error {
    ParseError(String),
}

impl std::fmt::Display for Error {
    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
        match *self {
            Error::ParseError(ref msg) => write!(f, "ParseError: {}", msg),
        }
    }
}

impl std::error::Error for Error {
    fn description(&self) -> &str {
        match *self {
            Error::ParseError(ref msg) => msg,
        }
    }

    fn cause(&self) -> Option<&std::error::Error> {
        match *self {
            Error::ParseError(_) => None,
        }
    }
}

#[derive(Serialize)]
pub struct Block {
    pub batches: Vec<Batch>,
    pub block_num: u64,
    #[serde(skip)]
    pub consensus: Vec<u8>,
    pub header_signature: String,
    pub previous_block_id: String,
    pub state_root_hash: String,
}

impl Block {
    pub fn try_from(block: messages::block::Block) -> Result<Self, Error> {
        protobuf::parse_from_bytes(&block.header)
            .map_err(|err| {
                Error::ParseError(format!(
                    "Invalid BlockHeader {}: {}",
                    block.header_signature, err
                ))
            }).and_then(|block_header: messages::block::BlockHeader| {
                block
                    .get_batches()
                    .iter()
                    .map(|batch| Batch::try_from(batch.clone()))
                    .collect::<Result<Vec<Batch>, Error>>()
                    .map(move |batches| Block {
                        batches: batches,
                        block_num: block_header.get_block_num(),
                        consensus: Vec::from(block_header.get_consensus()),
                        header_signature: String::from(block.get_header_signature()),
                        previous_block_id: String::from(block_header.get_previous_block_id()),
                        state_root_hash: String::from(block_header.get_state_root_hash()),
                    })
            })
    }
}

#[derive(Serialize)]
pub struct Batch {
    pub header_signature: String,
    pub signer_public_key: String,
    pub transactions: Vec<Transaction>,
}

impl Batch {
    pub fn try_from(batch: messages::batch::Batch) -> Result<Self, Error> {
        protobuf::parse_from_bytes(&batch.header)
            .map_err(|err| {
                Error::ParseError(format!(
                    "Invalid BatchHeader {}: {}",
                    batch.header_signature, err
                ))
            }).and_then(|batch_header: messages::batch::BatchHeader| {
                batch
                    .get_transactions()
                    .iter()
                    .map(|transaction| Transaction::try_from(&transaction.clone()))
                    .collect::<Result<Vec<Transaction>, Error>>()
                    .map(move |transactions| Batch {
                        header_signature: String::from(batch.get_header_signature()),
                        signer_public_key: String::from(batch_header.get_signer_public_key()),
                        transactions: transactions,
                    })
            })
    }
}

#[derive(Serialize)]
pub struct Transaction {
    pub batcher_public_key: String,
    pub dependencies: Vec<String>,
    pub family_name: String,
    pub family_version: String,
    pub header_signature: String,
    pub inputs: Vec<String>,
    pub nonce: String,
    pub outputs: Vec<String>,
    #[serde(skip)]
    pub payload: Vec<u8>,
    pub payload_sha512: String,
    pub signer_public_key: String,
}

impl Transaction {
    pub fn try_from(transaction: &messages::transaction::Transaction) -> Result<Self, Error> {
        protobuf::parse_from_bytes(&transaction.header)
            .map_err(|err| {
                Error::ParseError(format!(
                    "Invalid TransactionHeader {}: {}",
                    transaction.header_signature, err
                ))
            }).map(
                |transaction_header: messages::transaction::TransactionHeader| Transaction {
                    batcher_public_key: String::from(transaction_header.get_batcher_public_key()),
                    dependencies: transaction_header.get_dependencies().to_vec(),
                    family_name: String::from(transaction_header.get_family_name()),
                    family_version: String::from(transaction_header.get_family_version()),
                    header_signature: String::from(transaction.get_header_signature()),
                    inputs: transaction_header.get_inputs().to_vec(),
                    nonce: String::from(transaction_header.get_nonce()),
                    outputs: transaction_header.get_outputs().to_vec(),
                    payload: Vec::from(transaction.get_payload()),
                    payload_sha512: String::from(transaction_header.get_payload_sha512()),
                    signer_public_key: String::from(transaction_header.get_signer_public_key()),
                },
            )
    }
}
