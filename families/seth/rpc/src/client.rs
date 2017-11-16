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

use std::error::Error as StdError;
use std::fmt::{Display, Formatter, Result as FmtResult};
use std::str::FromStr;
use std::collections::HashMap;

use crypto::digest::Digest;
use crypto::sha2::Sha512;

use sawtooth_sdk::messaging::stream::*;
use sawtooth_sdk::messages::validator::Message_MessageType;
use sawtooth_sdk::messages::block::{Block};
use sawtooth_sdk::messages::client_receipt::{
    ClientReceiptGetRequest,
    ClientReceiptGetResponse,
    ClientReceiptGetResponse_Status,
};
use sawtooth_sdk::messages::client_block::{
    ClientBlockListRequest,
    ClientBlockListResponse,
    ClientBlockGetByIdRequest,
    ClientBlockGetByNumRequest,
    ClientBlockGetByTransactionIdRequest,
    ClientBlockGetResponse,
    ClientBlockGetResponse_Status,
};
use sawtooth_sdk::messages::client_state::{
    ClientStateGetRequest,
    ClientStateGetResponse,
    ClientStateGetResponse_Status,
};
use sawtooth_sdk::messages::client_transaction::{
    ClientTransactionGetRequest,
    ClientTransactionGetResponse,
    ClientTransactionGetResponse_Status,
};
use sawtooth_sdk::messages::client_batch_submit::{
    ClientBatchSubmitRequest,
    ClientBatchSubmitResponse,
    ClientBatchSubmitResponse_Status,
};
use sawtooth_sdk::messages::client_list_control::{
    ClientPagingControls,
};
use sawtooth_sdk::messages::transaction::{Transaction as TransactionPb, TransactionHeader};
use sawtooth_sdk::messages::batch::{Batch, BatchHeader};
use sawtooth_sdk::messages::block::{BlockHeader};
use messages::seth::{EvmEntry, EvmStateAccount, EvmStorage};
use accounts::{Account, Error as AccountError};
use filters::{FilterManager};
use transactions::{SethTransaction, SethReceipt, Transaction, TransactionKey};
use transform;

use protobuf;
use uuid;

#[derive(Clone)]
pub enum BlockKey {
    Latest,
    Earliest,
    Number(u64),
    Signature(String),
    Transaction(String),
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
const BLOCK_INFO_NS: &str = "00b10c";

#[derive(Debug)]
pub enum Error {
    ValidatorError,
    NoResource,
    CommunicationError(String),
    ParseError(String),
    AccountLoadError,
    SigningError,
    InvalidTransaction,
}

impl StdError for Error {
    fn description(&self) -> &str {
        match *self {
            Error::ValidatorError => "Validator returned internal error",
            Error::NoResource => "Resource not found",
            Error::CommunicationError(ref msg) => msg,
            Error::ParseError(ref msg) => msg,
            Error::AccountLoadError => "Account loading failed",
            Error::SigningError => "Signing failed",
            Error::InvalidTransaction => "Submitted transaction was invalid",
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
            Error::AccountLoadError => write!(f, "AccountLoadError"),
            Error::SigningError => write!(f, "SigningError"),
            Error::InvalidTransaction => write!(f, "InvalidTransaction"),
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

impl From<AccountError> for Error {
    fn from(error: AccountError) -> Self {
        match error {
            AccountError::ParseError(msg) => Error::ParseError(msg),
            AccountError::IoError(_) => Error::AccountLoadError,
            AccountError::AliasNotFound => Error::AccountLoadError,
            AccountError::SigningError => Error::SigningError,
        }
    }
}

#[derive(Clone)]
pub struct ValidatorClient<S: MessageSender> {
    sender: S,
    accounts: Vec<Account>,
    pub filters: FilterManager,
}

impl<S: MessageSender> ValidatorClient<S> {
    pub fn new(sender: S, accounts: Vec<Account>) -> Self {
        ValidatorClient{
            sender: sender,
            accounts: accounts,
            filters: FilterManager::new(),
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

    pub fn send_transaction(&mut self, from: &str, txn: SethTransaction) -> Result<String, Error> {
        let (batch, txn_signature) = self.make_batch(from, txn)?;

        let mut request = ClientBatchSubmitRequest::new();
        request.set_batches(protobuf::RepeatedField::from_vec(vec![batch]));

        let response: ClientBatchSubmitResponse =
            self.send_request(Message_MessageType::CLIENT_BATCH_SUBMIT_REQUEST, &request)?;

        match response.status {
            ClientBatchSubmitResponse_Status::STATUS_UNSET => Err(Error::ValidatorError),
            ClientBatchSubmitResponse_Status::OK => Ok(txn_signature),
            ClientBatchSubmitResponse_Status::INTERNAL_ERROR => Err(Error::ValidatorError),
            ClientBatchSubmitResponse_Status::INVALID_BATCH => Err(Error::InvalidTransaction),
        }
    }

    fn make_batch(&self, from: &str, txn: SethTransaction) -> Result<(Batch, String), Error> {
        let payload = protobuf::Message::write_to_bytes(&txn.to_pb()).map_err(|error|
            Error::ParseError(String::from(
                format!("Error serializing payload: {:?}", error))))?;

        let account = self.loaded_accounts().iter()
            .find(|account| account.address() == from)
            .ok_or_else(|| {
                error!("Account with address `{}` not found.", from);
                Error::NoResource})?;

        let mut txn_header = TransactionHeader::new();
        txn_header.set_batcher_public_key(String::from(account.public_key()));
        txn_header.set_family_name(String::from("seth"));
        txn_header.set_family_version(String::from("1.0"));
        txn_header.set_inputs(protobuf::RepeatedField::from_vec(
            vec![String::from(SETH_NS), String::from(BLOCK_INFO_NS)]));
        txn_header.set_outputs(protobuf::RepeatedField::from_vec(
            vec![String::from(SETH_NS), String::from(BLOCK_INFO_NS)]));

        let mut sha = Sha512::new();
        sha.input(&payload);
        let hash = sha.result_str();
        txn_header.set_payload_sha512(hash);

        txn_header.set_signer_public_key(String::from(account.public_key()));
        let txn_header_bytes = protobuf::Message::write_to_bytes(&txn_header).map_err(|error|
            Error::ParseError(String::from(
                format!("Error serializing transaction header: {:?}", error))))?;

        let txn_signature = account.sign(&txn_header_bytes)?;

        let mut txn = TransactionPb::new();
        txn.set_header(txn_header_bytes);
        txn.set_header_signature(txn_signature.clone());
        txn.set_payload(payload);

        let mut batch_header = BatchHeader::new();
        batch_header.set_signer_public_key(String::from(account.public_key()));
        batch_header.set_transaction_ids(protobuf::RepeatedField::from_vec(
            vec![txn_signature.clone()]));
        let batch_header_bytes = protobuf::Message::write_to_bytes(&batch_header).map_err(|error|
            Error::ParseError(String::from(
                format!("Error serializing batch header: {:?}", error))))?;

        let batch_signature = account.sign(&batch_header_bytes)?;

        let mut batch = Batch::new();
        batch.set_header(batch_header_bytes);
        batch.set_header_signature(batch_signature);
        batch.set_transactions(protobuf::RepeatedField::from_vec(vec![txn]));

        Ok((batch, txn_signature))
    }

    pub fn get_receipts_from_block(&mut self, block: &Block) -> Result<HashMap<String, SethReceipt>, String> {
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

        let receipts = self.get_receipts(&transactions).map_err(|error| match error {
            Error::ValidatorError => String::from("Received internal error from validator"),
            Error::NoResource => String::from("Missing receipt"),
            _ => String::from("Unknown error"),
        })?;

        Ok(receipts)
    }

    pub fn get_receipts(&mut self, transaction_ids: &[String])
        -> Result<HashMap<String, SethReceipt>, Error>
    {
        let mut request = ClientReceiptGetRequest::new();
        request.set_transaction_ids(protobuf::RepeatedField::from_vec(Vec::from(transaction_ids)));
        let response: ClientReceiptGetResponse =
            self.send_request(Message_MessageType::CLIENT_RECEIPT_GET_REQUEST, &request)?;

        let receipts = match response.status {
            ClientReceiptGetResponse_Status::STATUS_UNSET => {
                return Err(Error::ValidatorError);
            },
            ClientReceiptGetResponse_Status::OK => response.receipts,
            ClientReceiptGetResponse_Status::INTERNAL_ERROR => {
                return Err(Error::ValidatorError);
            },
            ClientReceiptGetResponse_Status::NO_RESOURCE => {
                return Err(Error::NoResource);
            },
        };
        let seth_receipt_list: Vec<SethReceipt> = receipts.iter()
            .map(SethReceipt::from_receipt_pb)
            .collect::<Result<Vec<SethReceipt>, Error>>()?;
        let mut seth_receipt_map = HashMap::with_capacity(seth_receipt_list.len());
        for receipt in seth_receipt_list.into_iter() {
            seth_receipt_map.insert(receipt.transaction_id.clone(), receipt);
        }

        Ok(seth_receipt_map)
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
                    self.get_block(BlockKey::Transaction(txn_id.clone())).ok()
                };

                match response.status {
                    ClientTransactionGetResponse_Status::STATUS_UNSET => {
                        Err(Error::ValidatorError)
                    },
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
        let response: ClientBlockGetResponse;
        match block_key {
            BlockKey::Signature(block_id) => {
                let mut request = ClientBlockGetByIdRequest::new();
                let message_type: Message_MessageType = Message_MessageType::CLIENT_BLOCK_GET_BY_ID_REQUEST;
                request.set_block_id(block_id);
                response = self.send_request(message_type, &request)?;
            },
            BlockKey::Number(block_num) => {
                let mut request = ClientBlockGetByNumRequest::new();
                let message_type: Message_MessageType = Message_MessageType::CLIENT_BLOCK_GET_BY_NUM_REQUEST;
                request.set_block_num(block_num);
                response = self.send_request(message_type, &request)?;
            },
            BlockKey::Latest => {
                return self.get_current_block();
            },
            BlockKey::Earliest => {
                let mut request = ClientBlockGetByIdRequest::new();
                let message_type: Message_MessageType = Message_MessageType::CLIENT_BLOCK_GET_BY_ID_REQUEST;
                request.set_block_id(String::from("0000000000000000"));
                response = self.send_request(message_type, &request)?;
            },
            BlockKey::Transaction(transaction_id) => {
                let mut request = ClientBlockGetByTransactionIdRequest::new();
                let message_type: Message_MessageType = Message_MessageType::CLIENT_BLOCK_GET_BY_TRANSACTION_ID_REQUEST;
                request.set_transaction_id(transaction_id);
                response = self.send_request(message_type, &request)?;
            },
        };

        match response.status {
            ClientBlockGetResponse_Status::STATUS_UNSET=> {
                Err(Error::ValidatorError)
            },
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
            BlockKey::Earliest => match self.block_id_to_state_root(
                    String::from("0000000000000000")) {
                Ok(state_root) => {
                    request.set_state_root(state_root);
                },
                Err(error) => {
                    return Err(String::from(format!("{:?}", error)));
                },
            },
            BlockKey::Signature(block_id) => match self.block_id_to_state_root(block_id) {
                Ok(state_root) => {
                    request.set_state_root(state_root);
                },
                Err(error) => {
                    return Err(String::from(format!("{:?}", error)));
                },
            },
            BlockKey::Number(block_num) => match self.block_num_to_state_root(block_num) {
                Ok(state_root) => {
                    request.set_state_root(state_root);
                },
                Err(error) => {
                    return Err(String::from(format!("{:?}", error)));
                },
            },
            BlockKey::Transaction(transaction_id) => match self.transaction_to_state_root(transaction_id) {
                Ok(state_root) => {
                    request.set_state_root(state_root);
                },
                Err(error) => {
                    return Err(String::from(format!("{:?}", error)));
                },
            },
        }

        let response: ClientStateGetResponse =
            self.request(Message_MessageType::CLIENT_STATE_GET_REQUEST, &request)?;

        let state_data = match response.status {
            ClientStateGetResponse_Status::STATUS_UNSET => {
                return Err(String::from("Internal error"));
            },
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
                let position = match transform::hex_str_to_bytes(&storage_address) {
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

    pub fn get_current_block(&mut self) -> Result<Block, Error> {
        let mut paging = ClientPagingControls::new();
        paging.set_count(1);
        let mut request = ClientBlockListRequest::new();
        request.set_paging(paging);

        let response: ClientBlockListResponse =
           self.send_request(Message_MessageType::CLIENT_BLOCK_LIST_REQUEST, &request)?;

        let block = &response.blocks[0];
        Ok(block.clone())
    }

    pub fn get_current_block_number(&mut self) -> Result<u64, Error> {
        let block = self.get_current_block()?;
        let block_header: BlockHeader = protobuf::parse_from_bytes(&block.header).map_err(|error|
            Error::ParseError(format!("Error parsing block_header: {:?}", error)))?;
        Ok(block_header.block_num)
    }

    pub fn get_blocks_since(&mut self, since: u64) -> Result<Vec<(u64, Block)>, Error> {
        let block = self.get_current_block()?;
        let block_header: BlockHeader = protobuf::parse_from_bytes(&block.header).map_err(|error|
            Error::ParseError(format!("Error parsing block_header: {:?}", error)))?;
        let block_num = block_header.block_num;
        if block_num <= since {
            return Ok(Vec::new());
        }

        let mut blocks = Vec::with_capacity((block_num - (since+1)) as usize);
        for block_num in (since+1)..block_num {
            let block = self.get_block(BlockKey::Number(block_num))?;
            let block_header: BlockHeader = protobuf::parse_from_bytes(&block.header).map_err(|error|
                Error::ParseError(format!("Error parsing block_header: {:?}", error)))?;
            let block_num = block_header.block_num;
            blocks.push((block_num, block));
        }
        blocks.push((block_num, block));

        Ok(blocks)
    }

    fn block_num_to_state_root(&mut self, block_num: u64) -> Result<String, Error> {
        self.get_block(BlockKey::Number(block_num)).and_then(|block|
            protobuf::parse_from_bytes(&block.header)
                .map_err(|error|
                    Error::ParseError(format!("Error parsing block_header: {:?}", error)))
                .map(|block_header: BlockHeader|
                    String::from(block_header.state_root_hash)))
    }

    fn block_id_to_state_root(&mut self, block_id: String) -> Result<String, Error> {
        self.get_block(BlockKey::Signature(block_id)).and_then(|block|
            protobuf::parse_from_bytes(&block.header)
                .map_err(|error|
                    Error::ParseError(format!("Error parsing block_header: {:?}", error)))
                .map(|block_header: BlockHeader|
                    String::from(block_header.state_root_hash)))
    }

    fn transaction_to_state_root(&mut self, transaction_id: String) -> Result<String, Error> {
        self.get_block(BlockKey::Transaction(transaction_id)).and_then(|block|
            protobuf::parse_from_bytes(&block.header)
                .map_err(|error|
                    Error::ParseError(format!("Error parsing block_header: {:?}", error)))
                .map(|block_header: BlockHeader|
                    String::from(block_header.state_root_hash)))
    }
}
