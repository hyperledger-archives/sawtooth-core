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

use std::fmt::LowerHex;
use std::str::FromStr;
use std::collections::HashMap;

use jsonrpc_core::{Value};

use sawtooth_sdk::messaging::stream::*;
use sawtooth_sdk::messages::validator::Message_MessageType;
use sawtooth_sdk::messages::block::{Block};
use sawtooth_sdk::messages::txn_receipt::{
    ClientReceiptGetRequest,
    ClientReceiptGetResponse,
    ClientReceiptGetResponse_Status,
};
use sawtooth_sdk::messages::client::{
    ClientBlockGetRequest,
    ClientBlockGetResponse,
    ClientBlockGetResponse_Status,
    ClientStateGetRequest,
    ClientStateGetResponse,
    ClientStateGetResponse_Status,
};
use sawtooth_sdk::messages::transaction::{TransactionHeader};
use super::messages::seth::{
    SethTransactionReceipt,
    EvmEntry, EvmStateAccount, EvmStorage,
};

use protobuf;
use uuid;


pub enum BlockKey {
    Latest,
    Earliest,
    Number(u64),
    Signature(String),
}

pub enum BlockKeyParseError {
    Unsupported,
    Invalid,
}

impl FromStr for BlockKey {
    type Err = BlockKeyParseError;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        if s == "latest" {
            Ok(BlockKey::Latest)
        } else if s == "earliest" {
            Ok(BlockKey::Earliest)
        } else if s == "pending" {
            Err(BlockKeyParseError::Unsupported)
        } else {
            if s.len() < 3 {
                Err(BlockKeyParseError::Invalid)
            } else {
                match u64::from_str_radix(&s[2..], 16) {
                    Ok(num) => Ok(BlockKey::Number(num)),
                    Err(_) => {
                        Err(BlockKeyParseError::Invalid)
                    },
                }
            }
        }
    }
}

const SETH_NS: &str = "a68b06";

#[derive(Clone)]
pub struct ValidatorClient<S: MessageSender> {
    sender: S,
}

impl<S: MessageSender> ValidatorClient<S> {
    pub fn new(sender: S) -> Self {
        ValidatorClient{ sender: sender }
    }

    pub fn request<T, U>(&mut self, msg_type: Message_MessageType, msg: &T) -> Result<U, String>
        where T: protobuf::Message, U: protobuf::MessageStatic
    {
        let msg_bytes = match protobuf::Message::write_to_bytes(msg) {
            Ok(b) => b,
            Err(error) => {
                return Err(String::from(format!("Error serializing request: {:?}", error)));
            },
        };

        let correlation_id = match uuid::Uuid::new(uuid::UuidVersion::Random) {
            Some(cid) => cid.to_string(),
            None => {
                return Err(String::from("Error generating UUID"));
            },
        };

        let mut future = match self.sender.send(msg_type, &correlation_id, &msg_bytes) {
            Ok(f) => f,
            Err(error) => {
                return Err(String::from(format!("Error unwrapping future: {:?}", error)));
            },
        };

        let response_msg = match future.get() {
            Ok(m) => m,
            Err(error) => {
                return Err(String::from(format!("Error getting future: {:?}", error)));
            },
        };

        let response: U = match protobuf::parse_from_bytes(&response_msg.content) {
            Ok(r) => r,
            Err(error) => {
                return Err(String::from(format!("Error parsing response: {:?}", error)));
            },
        };

        Ok(response)
    }

    pub fn get_receipts(&mut self, block: &Block) -> Result<HashMap<String, SethTransactionReceipt>, String> {
        let batches = &block.batches;
        let mut transactions = Vec::new();
        for batch in batches.iter() {
            for txn in batch.transactions.iter() {
                let header: TransactionHeader = match protobuf::parse_from_bytes(&txn.header) {
                    Ok(h) => h,
                    Err(_) => {
                        continue;
                    },
                };
                if header.family_name == "seth" {
                    transactions.push(String::from(txn.header_signature.clone()));
                }
            }
        }

        let mut request = ClientReceiptGetRequest::new();
        request.set_transaction_ids(protobuf::RepeatedField::from_vec(transactions));
        let response: ClientReceiptGetResponse =
            self.request(Message_MessageType::CLIENT_RECEIPT_GET_REQUEST, &request)?;

        let receipts = match response.status {
            ClientReceiptGetResponse_Status::OK => response.receipts,
            ClientReceiptGetResponse_Status::INTERNAL_ERROR => {
                return Err(String::from("Received internal error from validator"));
            },
            ClientReceiptGetResponse_Status::NO_RESOURCE => {
                return Err(String::from("Missing receipt"));
            }
        };
        let mut seth_receipts: HashMap<String, SethTransactionReceipt> = HashMap::new();
        for rcpt in receipts.iter() {
            for datum in rcpt.data.iter() {
                if datum.data_type == "seth_receipt" {
                    match protobuf::parse_from_bytes(&datum.data) {
                        Ok(seth_receipt) => {
                            seth_receipts.insert(rcpt.transaction_id.clone(), seth_receipt);
                        },
                        Err(error) => {
                            return Err(String::from(
                                format!("Failed to deserialize Seth receipt: {:?}", error)
                            ));
                        },
                    }
                }
            }
        }
        Ok(seth_receipts)
    }

    pub fn get_block(&mut self, block_key: BlockKey) -> Result<Option<Block>, String> {
        let mut request = ClientBlockGetRequest::new();
        match block_key {
            BlockKey::Signature(block_id) => request.set_block_id(block_id),
            BlockKey::Number(block_num) => request.set_block_num(block_num),
            BlockKey::Latest => {},
            BlockKey::Earliest => request.set_block_id(String::from("0000000000000000")),
        };

        let response: ClientBlockGetResponse =
            self.request(Message_MessageType::CLIENT_BLOCK_GET_REQUEST, &request)?;

        match response.status {
            ClientBlockGetResponse_Status::INTERNAL_ERROR => {
                Err(String::from("Received internal error from validator"))
            },
            ClientBlockGetResponse_Status::NO_RESOURCE => {
                Ok(None)
            },
            ClientBlockGetResponse_Status::OK => {
                Ok(response.block.into_option())
            },
        }
    }

    pub fn get_entry(&mut self, account_address: String, block: BlockKey) -> Result<Option<EvmEntry>, String> {
        let address = String::from(SETH_NS) + &account_address + "000000000000000000000000";
        let mut request = ClientStateGetRequest::new();
        request.set_address(address);
        match block {
            BlockKey::Latest => {},
            BlockKey::Earliest => {
                request.set_head_id(String::from("0000000000000000"));
            },
            BlockKey::Signature(block_id) => {
                request.set_head_id(block_id);
            },
            BlockKey::Number(block_num) => match self.block_num_to_block_id(block_num) {
                Ok(Some(block_id)) => {
                    request.set_head_id(block_id);
                },
                Ok(None) => {
                    return Err(String::from("Invalid block number"));
                },
                Err(error) => {
                    return Err(error);
                },
            },
        }

        let response: ClientStateGetResponse =
            self.request(Message_MessageType::CLIENT_STATE_GET_REQUEST, &request)?;

        let state_data = match response.status {
            ClientStateGetResponse_Status::OK => response.value,
            ClientStateGetResponse_Status::NO_RESOURCE => {
                return Ok(None);
            },
            ClientStateGetResponse_Status::INTERNAL_ERROR => {
                return Err(String::from("Internal error"));
            },
            ClientStateGetResponse_Status::NOT_READY => {
                return Err(String::from("Validator isn't ready"));
            },
            ClientStateGetResponse_Status::NO_ROOT => {
                return Err(String::from("No root"));
            },
            ClientStateGetResponse_Status::INVALID_ADDRESS => {
                return Err(String::from("Invalid address"));
            },
        };

        match protobuf::parse_from_bytes(&state_data) {
            Ok(e) => Ok(Some(e)),
            Err(error) => {
                Err(String::from(format!("Failed to deserialize EVM entry: {:?}", error)))
            },
        }
    }

    pub fn get_account(&mut self, account_address: String, block: BlockKey) -> Result<Option<EvmStateAccount>, String> {
        self.get_entry(account_address, block).map(|option|
            option.map(|mut entry| entry.take_account()))
    }

    pub fn get_storage(&mut self, account_address: String, block: BlockKey) -> Result<Option<Vec<EvmStorage>>, String> {
        self.get_entry(account_address, block).map(|option|
            option.map(|mut entry| entry.take_storage().into_vec()))
    }

    pub fn get_storage_at(&mut self, account_address: String, storage_address: String, block: BlockKey) -> Result<Option<Vec<u8>>, String> {
        let storage = self.get_storage(account_address, block)?;

        match storage {
            Some(storage) => {
                let position = match hex_to_bytes(&storage_address) {
                    Some(p) => p,
                    None => {
                        return Err(String::from("Failed to decode position, invalid hex."));
                    }
                };
                for entry in storage.into_iter() {
                    if entry.key == position {
                        return Ok(Some(Vec::from(entry.value)));
                    }
                }
                return Ok(None);
            },
            None => {
                return Ok(None);
            }
        }
    }

    fn block_num_to_block_id(&mut self, block_num: u64) -> Result<Option<String>, String> {
        self.get_block(BlockKey::Number(block_num)).map(|option|
            option.map(|block|
                String::from(block.header_signature)))
    }
}



pub fn num_to_hex<T>(n: &T) -> Value where T: LowerHex {
    Value::String(String::from(format!("{:#x}", n)))
}

pub fn string_to_hex(s: &str) -> Value {
    Value::String(String::from(format!("0x{}", s)))
}

pub fn bytes_to_hex(bytes: &[u8]) -> Value {
    let mut s = String::from("0x");
    for &b in bytes.iter() {
        s.push_str(&(format!("{:x}", b)))
    }
    Value::String(s)
}

pub fn hex_to_bytes(hex: &str) -> Option<Vec<u8>> {
    if hex.len() % 2 != 0 {
        return None
    }

    let mut string = String::from(hex);
    let mut bytes = Vec::new();
    while string.len() > 0 {
        let a = string.pop().unwrap();
        let b = string.pop().unwrap();
        let mut c = String::new();
        c.push(b);
        c.push(a);
        match u8::from_str_radix(&c, 16) {
            Ok(x) => bytes.push(x),
            Err(_) => {
                return None;
            }
        }
    }
    bytes.reverse();
    Some(bytes)
}
