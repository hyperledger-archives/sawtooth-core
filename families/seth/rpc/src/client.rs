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

use std::sync::{Arc, Mutex};
use std::error::Error as StdError;
use std::fmt::{LowerHex, Display, Formatter, Result as FmtResult};
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
    ClientBlockListRequest,
    ClientBlockListResponse,
    ClientBlockGetRequest,
    ClientBlockGetResponse,
    ClientBlockGetResponse_Status,
    ClientStateGetRequest,
    ClientStateGetResponse,
    ClientStateGetResponse_Status,
    PagingControls,
    ClientTransactionGetRequest,
    ClientTransactionGetResponse,
    ClientTransactionGetResponse_Status,
};
use sawtooth_sdk::messages::transaction::{TransactionHeader};
use messages::seth::{
    SethTransactionReceipt,
    EvmEntry, EvmStateAccount, EvmStorage,
};
use accounts::{Account};
use filters::Filter;
use transactions::{Transaction, TransactionKey};

use protobuf;
use uuid;

#[derive(Clone)]
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

#[derive(Debug)]
pub enum Error {
    ValidatorError,
    NoResource,
    CommunicationError(String),
    ParseError(String),
}

impl StdError for Error {
    fn description(&self) -> &str {
        match *self {
            Error::ValidatorError => "Validator returned internal error",
            Error::NoResource => "Resource not found",
            Error::CommunicationError(ref msg) => msg,
            Error::ParseError(ref msg) => msg,
        }
    }

    fn cause(&self) -> Option<&StdError> { None }
}

impl Display for Error {
    fn fmt(&self, f: &mut Formatter) -> FmtResult {
        match *self {
            Error::ValidatorError => write!(f, "ValidatorError"),
            Error::NoResource => write!(f, "NoResource"),
            Error::CommunicationError(ref msg) => write!(f, "CommunicationError: {}", msg),
            Error::ParseError(ref msg) => write!(f, "ParseError: {}", msg),
        }
    }
}

impl From<SendError> for Error {
    fn from(error: SendError) -> Self {
        Error::CommunicationError(String::from(
            format!("Failed to send msg: {:?}", error)))
    }
}

impl From<ReceiveError> for Error {
    fn from(error: ReceiveError) -> Self {
        Error::CommunicationError(String::from(
            format!("Failed to receive message: {:?}", error)))
    }
}

#[derive(Clone)]
pub struct ValidatorClient<S: MessageSender> {
    sender: S,
    accounts: Vec<Account>,
    filters: Arc<Mutex<HashMap<String, (Filter, String)>>>
}

impl<S: MessageSender> ValidatorClient<S> {
    pub fn new(sender: S, accounts: Vec<Account>) -> Self {
        ValidatorClient{
            sender: sender,
            accounts: accounts,
            filters: Arc::new(Mutex::new(HashMap::new()))
        }
    }

    pub fn loaded_accounts(&self) -> &[Account] {
        &self.accounts
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

    pub fn send_request<T, U>(&mut self, msg_type: Message_MessageType, msg: &T) -> Result<U, Error>
        where T: protobuf::Message, U: protobuf::MessageStatic
    {
        let msg_bytes = protobuf::Message::write_to_bytes(msg).map_err(|error|
            Error::ParseError(String::from(
                format!("Error serializing request: {:?}", error))))?;

        let correlation_id = uuid::Uuid::new_v4().to_string();

        let mut future = self.sender.send(msg_type, &correlation_id, &msg_bytes)?;
        let response_msg = future.get()?;
        protobuf::parse_from_bytes(&response_msg.content).map_err(|error|
            Error::ParseError(String::from(format!("Error parsing response: {:?}", error))))
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

    pub fn get_transaction_and_block(&mut self, txn_key: &TransactionKey) -> Result<(Transaction, Option<Block>), Error> {
        match txn_key {
            &TransactionKey::Signature(ref txn_id) => {
                let mut request = ClientTransactionGetRequest::new();
                request.set_transaction_id((*txn_id).clone());
                let mut response: ClientTransactionGetResponse =
                    self.send_request(
                        Message_MessageType::CLIENT_TRANSACTION_GET_REQUEST, &request)?;

                let block = {
                    if response.block == "" {
                        None
                    } else {
                        self.get_block(BlockKey::Signature(response.block.clone())).ok()
                    }
                };

                match response.status {
                    ClientTransactionGetResponse_Status::INTERNAL_ERROR => {
                        Err(Error::ValidatorError)
                    },
                    ClientTransactionGetResponse_Status::NO_RESOURCE => {
                        Err(Error::NoResource)
                    },
                    ClientTransactionGetResponse_Status::OK => {
                        let txn = Transaction::try_from(response.take_transaction())?;
                        Ok((txn, block))
                    },
                }
            },
            &TransactionKey::Index((ref index, ref block_key)) => {
                let mut idx = *index;
                let mut block = self.get_block((*block_key).clone())?;
                for mut batch in block.take_batches().into_iter() {
                    for txn in batch.take_transactions().into_iter() {
                        if idx == 0 {
                            let txn = Transaction::try_from(txn)?;
                            return Ok((txn, Some(block)));
                        }
                        idx -= 1;
                    }
                }
                Err(Error::NoResource)
            }
        }
    }

    pub fn get_block(&mut self, block_key: BlockKey) -> Result<Block, Error> {
        let mut request = ClientBlockGetRequest::new();
        match block_key {
            BlockKey::Signature(block_id) => request.set_block_id(block_id),
            BlockKey::Number(block_num) => request.set_block_num(block_num),
            BlockKey::Latest => {},
            BlockKey::Earliest => request.set_block_id(String::from("0000000000000000")),
        };

        let response: ClientBlockGetResponse =
            self.send_request(Message_MessageType::CLIENT_BLOCK_GET_REQUEST, &request)?;

        match response.status {
            ClientBlockGetResponse_Status::INTERNAL_ERROR => {
                Err(Error::ValidatorError)
            },
            ClientBlockGetResponse_Status::NO_RESOURCE => {
                Err(Error::NoResource)
            },
            ClientBlockGetResponse_Status::OK => {
                if let Some(block) = response.block.into_option() {
                    Ok(block)
                } else {
                    Err(Error::NoResource)
                }
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
                Ok(block_id) => {
                    request.set_head_id(block_id);
                },
                Err(error) => {
                    return Err(String::from(format!("{:?}", error)));
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
                let position = match hex_str_to_bytes(&storage_address) {
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

    pub fn get_current_block(&mut self) -> Result<Block, String> {
        let mut paging = PagingControls::new();
        paging.set_count(1);
        let mut request = ClientBlockListRequest::new();
        request.set_paging(paging);

        let response: ClientBlockListResponse =
           self.request(Message_MessageType::CLIENT_BLOCK_LIST_REQUEST, &request)?;

        let block = &response.blocks[0];
        Ok(block.clone())
    }

    fn block_num_to_block_id(&mut self, block_num: u64) -> Result<String, Error> {
        self.get_block(BlockKey::Number(block_num)).map(|block|
            String::from(block.header_signature))
    }

    pub fn remove_filter(&mut self, filter_id: &String) -> Option<(Filter, String)> {
        self.filters.lock().unwrap().remove(filter_id)
    }

    pub fn get_filter(&mut self, filter_id: &String) -> Result<(Filter, String), String> {
        let filters = self.filters.lock().unwrap();
        if filters.contains_key(filter_id) {
            Ok(filters[filter_id].clone())
        } else {
            Err(format!("Unknown filter id: {:?}", filter_id))
        }
    }

    pub fn set_filter(&mut self, filter_id: String, filter: Filter, block_id: String) {
        let mut filters = self.filters.lock().unwrap();
        let entry = filters.entry(filter_id).or_insert((filter, block_id.clone()));
        (*entry).1 = block_id
    }

}



pub fn num_to_hex<T>(n: &T) -> Value where T: LowerHex {
    Value::String(String::from(format!("{:#x}", n)))
}

pub fn hex_prefix(s: &str) -> Value {
    Value::String(String::from(format!("0x{}", s)))
}

pub fn hex_str_to_bytes(s: &str) -> Option<Vec<u8>> {
    for ch in s.chars() {
        if !ch.is_digit(16) {
            return None
        }
    }

    let input: Vec<_> = s.chars().collect();

    let decoded: Vec<u8> = input.chunks(2).map(|chunk| {
        ((chunk[0].to_digit(16).unwrap() << 4) |
        (chunk[1].to_digit(16).unwrap())) as u8
    }).collect();

    return Some(decoded);
}

pub fn bytes_to_hex_str(b: &[u8]) -> String {
    b.iter()
     .map(|b| format!("{:02x}", b))
     .collect::<Vec<_>>()
     .join("")
}

pub fn zerobytes(mut nbytes: usize) -> Value {
    if nbytes == 0 {
        return Value::String(String::from("0x0"));
    }
    let mut s = String::with_capacity(2 + nbytes * 2);
    while nbytes > 0 {
        s.push_str("00");
        nbytes -= 1;
    }
    s.push_str("0x");
    Value::String(s)
}
