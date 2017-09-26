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
use std::collections::HashMap;

use futures_cpupool::{CpuPool};
use jsonrpc_core::{Params, Value, Error, BoxFuture};

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
};
use sawtooth_sdk::messages::transaction::{TransactionHeader};
use super::messages::seth::{SethTransactionReceipt};

use protobuf;
use uuid;


pub type RequestHandler<T> = fn(Params, ValidatorClient<T>) -> Result<Value, Error>;

#[derive(Clone)]
pub struct RequestExecutor<T: MessageSender + Clone + Sync + Send + 'static> {
    pool: CpuPool,
    client: ValidatorClient<T>,
}

impl<T: MessageSender + Clone + Sync + Send + 'static> RequestExecutor<T> {
    pub fn new(sender: T) -> Self {
        RequestExecutor {
            pool: CpuPool::new_num_cpus(),
            client: ValidatorClient::new(sender),
        }
    }

    pub fn run(&self, params: Params, handler: RequestHandler<T>) -> BoxFuture<Value, Error> {
        let client = self.client.clone();
        Box::new(self.pool.spawn_fn(move || {handler(params, client)}))
    }

}

pub enum BlockKey {
    Number(u64),
    Signature(String),
}

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
}

pub fn num_to_hex<T>(n: &T) -> Value where T: LowerHex {
    Value::String(String::from(format!("{:#x}", n)))
}

pub fn string_to_hex(s: &str) -> Value {
    Value::String(String::from(format!("0x{}", s)))
}
