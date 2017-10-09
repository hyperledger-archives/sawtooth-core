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

use jsonrpc_core::{Params, Value, Error};
use serde_json::Map;
use protobuf;

use error;
use requests::{RequestHandler};

use client::{
    ValidatorClient,
    Error as ClientError,
    BlockKey,
};
use transform;

use sawtooth_sdk::messaging::stream::*;

use sawtooth_sdk::messages::block::BlockHeader;

pub fn get_method_list<T>() -> Vec<(String, RequestHandler<T>)> where T: MessageSender {
    let mut methods: Vec<(String, RequestHandler<T>)> = Vec::new();

    methods.push((String::from("eth_blockNumber"), block_number));
    methods.push((String::from("eth_getBlockByHash"), get_block_by_hash));
    methods.push((String::from("eth_getBlockByNumber"), get_block_by_number));
    methods.push((String::from("eth_getBlockTransactionCountByHash"), get_block_transaction_count_by_hash));
    methods.push((String::from("eth_getBlockTransactionCountByNumber"), get_block_transaction_count_by_number));

    methods
}

// Return the block number of the current chain head, in hex, as a string
pub fn block_number<T>(_params: Params, mut client: ValidatorClient<T>) -> Result<Value, Error> where T: MessageSender {
    info!("eth_blockNumber");
    let block = client.get_current_block().map_err(|err| {
        error!("Error requesting block: {:?}", err);
        Error::internal_error()
    })?;
    let block_header: BlockHeader = match protobuf::parse_from_bytes(&block.header) {
        Ok(r) => r,
        Err(error) => {
            error!("Error parsing block header: {:?}", error);
            return Err(Error::internal_error());
        }
    };

    Ok(Value::String(format!("{:#x}", block_header.block_num).into()))
}

fn get_block_obj<T>(block_key: BlockKey, mut client: ValidatorClient<T>) -> Result<Value, Error> where T: MessageSender {
    let block = match client.get_block(block_key) {
        Ok(b) => b,
        Err(error) => match error {
            ClientError::NoResource => {
                return Ok(Value::Null);
            },
            _ => {
                error!("{:?}", error);
                return Err(Error::internal_error());
            }
        }
    };

    let block_header: BlockHeader = match protobuf::parse_from_bytes(&block.header) {
        Ok(r) => r,
        Err(error) => {
            error!("Error parsing block header: {:?}", error);
            return Err(Error::internal_error());
        },
    };

    let mut bob = Map::new();
    bob.insert(String::from("number"), transform::num_to_hex(&block_header.block_num));
    bob.insert(String::from("hash"), transform::hex_prefix(&block.header_signature));
    bob.insert(String::from("parentHash"), transform::hex_prefix(&block_header.previous_block_id));
    bob.insert(String::from("stateRoot"), transform::hex_prefix(&block_header.state_root_hash));

    let receipts = match client.get_receipts_from_block(&block) {
        Ok(r) => r,
        Err(error) => {
            error!("Error getting receipts: {:?}", error);
            return Err(Error::internal_error());
        }
    };
    let mut transactions = Vec::new();
    let mut gas: u64 = 0;
    for (txn_id, receipt) in receipts.into_iter() {
        transactions.push(transform::hex_prefix(&txn_id));
        gas += receipt.gas_used;
    }
    bob.insert(String::from("transactions"), Value::Array(transactions));
    bob.insert(String::from("gasUsed"), transform::num_to_hex(&gas));

    // No corollaries in Sawtooth
    bob.insert(String::from("nonce"), transform::zerobytes(8));
    bob.insert(String::from("sha3Uncles"), transform::zerobytes(32));
    bob.insert(String::from("logsBloom"), transform::zerobytes(256));
    bob.insert(String::from("transactionsRoot"), transform::zerobytes(32));
    bob.insert(String::from("receiptsRoot"), transform::zerobytes(32));
    bob.insert(String::from("miner"), transform::zerobytes(20));
    bob.insert(String::from("difficulty"), transform::zerobytes(0));
    bob.insert(String::from("totalDifficulty"), transform::zerobytes(0));
    bob.insert(String::from("extraData"), transform::zerobytes(0));
    bob.insert(String::from("size"), transform::zerobytes(0));
    bob.insert(String::from("gasLimit"), transform::zerobytes(0));
    bob.insert(String::from("uncles"), Value::Array(Vec::new()));

    Ok(Value::Object(bob))

}

fn get_block_transaction_count<T>(block_key: BlockKey, mut client: ValidatorClient<T>) -> Result<Value, Error> where T: MessageSender {
    let block = match client.get_block(block_key) {
        Ok(b) => b,
        Err(error) => match error {
            ClientError::NoResource => {
                return Ok(Value::Null);
            },
            _ => {
                error!("{:?}", error);
                return Err(Error::internal_error());
            }
        }
    };

    Ok(transform::num_to_hex(&block.batches.iter().fold(0, |acc, batch| acc + batch.transactions.len())))
}

// Returns a block object using its "hash" to identify it. In Sawtooth, this is the blocks
// signature, which is 64 bytes instead of 32.
pub fn get_block_by_hash<T>(params: Params, client: ValidatorClient<T>) -> Result<Value, Error> where T: MessageSender {
    info!("eth_getBlockByHash");
    let (block_hash, full): (String, bool) = match params.parse() {
        Ok(t) => t,
        Err(_) => {
            return Err(Error::invalid_params("Takes [blockHash: DATA(64), full: BOOL]"));
        },
    };
    let block_hash = match block_hash.get(2..) {
        Some(bh) => String::from(bh),
        None => {
            return Err(Error::invalid_params("Invalid block hash, must have 0x"));
        }
    };
    if full {
        return Err(error::not_implemented());
    }

    get_block_obj(BlockKey::Signature(block_hash), client)
}

pub fn get_block_by_number<T>(params: Params, client: ValidatorClient<T>) -> Result<Value, Error> where T: MessageSender {
    info!("eth_getBlockByNumber");
    let (block_num, full): (String, bool) = match params.parse() {
        Ok(t) => t,
        Err(_) => {
            return Err(Error::invalid_params("Takes [blockNum: QUANTITY, full: BOOL]"));
        },
    };

    if block_num.len() < 3 {
        return Err(Error::invalid_params("Invalid block number"));
    }

    let block_num = match u64::from_str_radix(&block_num[2..], 16) {
        Ok(num) => num,
        Err(error) => {
            return Err(Error::invalid_params(
                format!("Failed to parse block number: {:?}", error)));
        },
    };

    if full {
        return Err(error::not_implemented());
    }

    get_block_obj(BlockKey::Number(block_num), client)
}

// Returns the number of transactions in a block
pub fn get_block_transaction_count_by_hash<T>(params: Params, client: ValidatorClient<T>) -> Result<Value, Error> where T: MessageSender {
    info!("eth_getBlockTransactionCountByHash");
    let (block_hash,): (String,) = match params.parse() {
        Ok(t) => t,
        Err(_) => {
            return Err(Error::invalid_params("Takes [blockHash: DATA(64)]"));
        },
    };
    let block_hash = match block_hash.get(2..) {
        Some(bh) => String::from(bh),
        None => {
            return Err(Error::invalid_params("Invalid block hash, must have 0x"));
        }
    };
    get_block_transaction_count(BlockKey::Signature(block_hash), client)
}

pub fn get_block_transaction_count_by_number<T>(params: Params, client: ValidatorClient<T>) -> Result<Value, Error> where T: MessageSender {
    info!("eth_getBlockTransactionCountByNumber");
    let (block_num,): (String,) = match params.parse() {
        Ok(t) => t,
        Err(_) => {
            return Err(Error::invalid_params("Takes [blockNum: QUANTITY]"));
        },
    };

    if block_num.len() < 3 {
        return Err(Error::invalid_params("Invalid block number"));
    }

    let block_num = match u64::from_str_radix(&block_num[2..], 16) {
        Ok(num) => num,
        Err(error) => {
            return Err(Error::invalid_params(
                format!("Failed to parse block number: {:?}", error)));
        },
    };
    get_block_transaction_count(BlockKey::Number(block_num), client)
}
