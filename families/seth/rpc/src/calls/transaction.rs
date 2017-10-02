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

use protobuf;
use jsonrpc_core::{Params, Value, Error};
use serde_json::Map;

use client::{
    ValidatorClient,
    BlockKey,
    Error as ClientError,
    num_to_hex,
    hex_prefix,
    zerobytes,
};

use sawtooth_sdk::messages::block::BlockHeader;
use sawtooth_sdk::messaging::stream::MessageSender;
use error;
use requests::{RequestHandler};
use transactions::{TransactionKey, Transaction};

pub fn get_method_list<T>() -> Vec<(String, RequestHandler<T>)> where T: MessageSender {
    let mut methods: Vec<(String, RequestHandler<T>)> = Vec::new();

    methods.push((String::from("eth_sendTransaction"), send_transaction));
    methods.push((String::from("eth_sendRawTransaction"), send_raw_transaction));
    methods.push((String::from("eth_getTransactionByHash"), get_transaction_by_hash));
    methods.push((String::from("eth_getTransactionByBlockHashAndIndex"), get_transaction_by_block_hash_and_index));
    methods.push((String::from("eth_getTransactionByBlockNumberAndIndex"), get_transaction_by_block_number_and_index));
    methods.push((String::from("eth_getTransactionReceipt"), get_transaction_receipt));
    methods.push((String::from("eth_gasPrice"), gas_price));
    methods.push((String::from("eth_estimateGas"), estimate_gas));
    methods.push((String::from("eth_sign"), sign));
    methods.push((String::from("eth_call"), call));

    methods
}

pub fn send_transaction<T>(_params: Params, mut _client: ValidatorClient<T>) -> Result<Value, Error> where T: MessageSender {
    Err(error::not_implemented())
}
pub fn send_raw_transaction<T>(_params: Params, mut _client: ValidatorClient<T>) -> Result<Value, Error> where T: MessageSender {
    Err(error::not_implemented())
}
pub fn get_transaction_by_hash<T>(params: Params, client: ValidatorClient<T>) -> Result<Value, Error> where T: MessageSender {
    info!("eth_getTransactionByHash");
    let (txn_hash,): (String,) = match params.parse() {
        Ok(t) => t,
        Err(_) => {
            return Err(Error::invalid_params("Takes [txnHash: DATA(64)]"));
        },
    };
    let txn_hash = match txn_hash.get(2..) {
        Some(th) => String::from(th),
        None => {
            return Err(Error::invalid_params("Invalid transaction hash, must have 0x"));
        }
    };

    get_transaction(client, &TransactionKey::Signature(txn_hash))
}
pub fn get_transaction_by_block_hash_and_index<T>(params: Params, client: ValidatorClient<T>) -> Result<Value, Error> where T: MessageSender {
    info!("eth_getTransactionByBlockHashAndIndex");
    let (block_hash, index): (String, String) = match params.parse() {
        Ok(t) => t,
        Err(_) => {
            return Err(Error::invalid_params("Takes [blockHash: DATA(64), index: QUANTITY]"));
        },
    };
    let block_hash = match block_hash.get(2..) {
        Some(bh) => String::from(bh),
        None => {
            return Err(Error::invalid_params("Invalid block hash, must have 0x"));
        }
    };

    if index.len() < 3 {
        return Err(Error::invalid_params("Invalid transaction index"));
    }
    let index = match u64::from_str_radix(&index[2..], 16) {
        Ok(num) => num,
        Err(error) => {
            return Err(Error::invalid_params(
                format!("Failed to parse transaction index: {:?}", error)));
        },
    };

    get_transaction(client, &TransactionKey::Index((index, BlockKey::Signature(block_hash))))
}

pub fn get_transaction_by_block_number_and_index<T>(params: Params, client: ValidatorClient<T>) -> Result<Value, Error> where T: MessageSender {
    info!("eth_getTransactionByBlockNumberAndIndex");
    let (block_num, index): (String, String) = match params.parse() {
        Ok(t) => t,
        Err(_) => {
            return Err(Error::invalid_params("Takes [blockNum: DATA(64), index: QUANTITY]"));
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

    if index.len() < 3 {
        return Err(Error::invalid_params("Invalid transaction index"));
    }
    let index = match u64::from_str_radix(&index[2..], 16) {
        Ok(num) => num,
        Err(error) => {
            return Err(Error::invalid_params(
                format!("Failed to parse transaction index: {:?}", error)));
        },
    };

    get_transaction(client, &TransactionKey::Index((index, BlockKey::Number(block_num))))
}

fn get_transaction<T>(mut client: ValidatorClient<T>, txn_key: &TransactionKey) -> Result<Value, Error> where T: MessageSender {
    let (txn, block) = match client.get_transaction_and_block(txn_key) {
        Ok(t) => t,
        Err(error) => match error {
            ClientError::NoResource => {
                return Ok(Value::Null);
            },
            _ => {
                error!("{:?}", error);
                return Err(Error::internal_error());
            },
        },
    };

    match block {
        Some(mut block) => {
            let block_header: BlockHeader = match protobuf::parse_from_bytes(&block.header) {
                Ok(r) => r,
                Err(error) => {
                    error!("Error parsing block header: {:?}", error);
                    return Err(Error::internal_error());
                }
            };
            // We know the transaction index already, because get_transaction_and_block succeeded
            match txn_key {
                &TransactionKey::Index((index, _)) =>
                    Ok(make_txn_obj(txn, index, &block.header_signature, block_header.block_num)),
                &TransactionKey::Signature(ref txn_id) => {
                    let txn_id = (*txn_id).clone();
                    let mut index = 0;
                    for mut batch in block.take_batches().into_iter() {
                        for transaction in batch.take_transactions().into_iter() {
                            if transaction.header_signature == txn_id {
                                return Ok(make_txn_obj(
                                    txn, index, &block.header_signature, block_header.block_num));
                            }
                            index += 1;
                        }
                    }
                    // This should never happen, because we fetched the block and transaction
                    // together.
                    return Err(Error::internal_error());
                }
            }
        }
        None => {
            // Transaction exists, but isn't in a block yet
            Ok(make_txn_obj_no_block(txn))
        }
    }

}
pub fn get_transaction_receipt<T>(_params: Params, mut _client: ValidatorClient<T>) -> Result<Value, Error> where T: MessageSender {
    Err(error::not_implemented())
}
pub fn gas_price<T>(_params: Params, mut _client: ValidatorClient<T>) -> Result<Value, Error> where T: MessageSender {
    info!("eth_gasPrice");
    Ok(Value::String(format!("{:#x}", 0)))
}
pub fn estimate_gas<T>(_params: Params, mut _client: ValidatorClient<T>) -> Result<Value, Error> where T: MessageSender {
    Err(error::not_implemented())
}
pub fn sign<T>(_params: Params, mut _client: ValidatorClient<T>) -> Result<Value, Error> where T: MessageSender {
    Err(error::not_implemented())
}
pub fn call<T>(_params: Params, mut _client: ValidatorClient<T>) -> Result<Value, Error> where T: MessageSender {
    Err(error::not_implemented())
}

fn make_txn_obj(txn: Transaction, txn_idx: u64, block_hash: &str, block_num: u64) -> Value {
    let obj = make_txn_obj_no_block(txn);
    if let Value::Object(mut map) = obj {
        map.insert(String::from("blockHash"), hex_prefix(block_hash));
        map.insert(String::from("blockNumber"), num_to_hex(&block_num));
        map.insert(String::from("transactionIndex"), num_to_hex(&txn_idx));
        Value::Object(map)
    } else {
        obj
    }
}

fn make_txn_obj_no_block(txn: Transaction) -> Value {
    let mut map = Map::with_capacity(11);
    map.insert(String::from("hash"), hex_prefix(&txn.hash()));
    map.insert(String::from("nonce"), num_to_hex(&txn.nonce()));
    map.insert(String::from("blockHash"), Value::Null);
    map.insert(String::from("blockNumber"), Value::Null);
    map.insert(String::from("transactionIndex"), Value::Null);
    map.insert(String::from("from"), hex_prefix(&txn.from_addr()));
    let to = match txn.to_addr() {
        Some(addr) => hex_prefix(&addr),
        None => Value::Null,
    };
    map.insert(String::from("to"), to);

    map.insert(String::from("value"), zerobytes(0));
    map.insert(String::from("gasPrice"), zerobytes(0));

    let gas = match txn.gas_limit() {
        Some(g) => num_to_hex(&g),
        None => zerobytes(0),
    };
    map.insert(String::from("gas"), gas);

    let input = match txn.data() {
        Some(data) => hex_prefix(&data),
        None => zerobytes(0),
    };
    map.insert(String::from("input"), input);
    Value::Object(map)
}
