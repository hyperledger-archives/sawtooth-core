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
use tiny_keccak;

use client::{
    ValidatorClient,
    BlockKey,
    Error as ClientError,
    num_to_hex,
    hex_prefix,
    hex_str_to_bytes,
    zerobytes,
};

use sawtooth_sdk::messages::block::BlockHeader;
use sawtooth_sdk::messaging::stream::MessageSender;
use error;
use requests::{RequestHandler};
use transactions::{TransactionKey, Transaction, SethTransaction, SethReceipt, SethLog};

use messages::seth::{
    CreateContractAccountTxn as CreateContractAccountTxnPb,
    MessageCallTxn as MessageCallTxnPb,
};

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

fn get_from_map<F,T>(map: &Map<String, Value>, key: &str, f: F) -> Result<Option<T>, Error>
    where F: FnOnce(&str) -> Result<T, Error>
{
    if let Some(value) = map.get(key) {
        value.as_str()
            .ok_or_else(|| Error::invalid_params(format!("`{}` not a string", key)))
            .and_then(|v| v.get(2..).ok_or_else(||
                Error::invalid_params(format!("`{}` must have 0x", key))))
            .and_then(f)
            .map(|v| Some(v))
    } else {
        Ok(None)
    }
}

fn get_u64_from_map(map: &Map<String, Value>, key: &str) -> Result<Option<u64>, Error> {
    get_from_map(map, key, |v| u64::from_str_radix(v, 16).map_err(|error|
        Error::invalid_params(format!("`{}` not a number: {:?}", key, error))))
}

fn get_bytes_from_map(map: &Map<String, Value>, key: &str) -> Result<Option<Vec<u8>>, Error> {
    get_from_map(map, key, |v| hex_str_to_bytes(v).ok_or_else(||
        Error::invalid_params(format!("`{}` not valid hex", key))))
}

fn get_string_from_map(map: &Map<String, Value>, key: &str) -> Result<Option<String>, Error> {
    get_from_map(map, key, |v| Ok(String::from(v)))
}

pub fn send_transaction<T>(params: Params, mut client: ValidatorClient<T>) -> Result<Value, Error> where T: MessageSender {
    info!("eth_sendTransaction");
    let (txn,): (Map<String, Value>,) = params.parse().map_err(|_|
        Error::invalid_params("Takes [txn: OBJECT]"))?;

    // Required arguments
    let from = get_string_from_map(&txn, "from").and_then(|f| f.ok_or_else(||
        Error::invalid_params("`from` not set")))?;
    let data = get_bytes_from_map(&txn, "data").and_then(|f| f.ok_or_else(||
        Error::invalid_params("`data` not set")))?;

    // Optional Arguments
    let to = get_bytes_from_map(&txn, "to")?;
    let gas = get_u64_from_map(&txn, "gas").map(|g| g.unwrap_or(90000))?;
    let gas_price = get_u64_from_map(&txn, "gasPrice").map(|g| g.unwrap_or(10000000000000))?;
    let value = get_u64_from_map(&txn, "value").map(|g| g.unwrap_or(0))?;
    let nonce = get_u64_from_map(&txn, "nonce").map(|g| g.unwrap_or(0))?;

    let txn = if let Some(to) = to {
        // Message Call
        let mut txn = MessageCallTxnPb::new();
        txn.set_to(to);
        txn.set_data(data);
        txn.set_gas_limit(gas);
        txn.set_gas_price(gas_price);
        txn.set_value(value);
        txn.set_nonce(nonce);
        SethTransaction::MessageCall(txn)
    } else {
        // Contract Creation
        let mut txn = CreateContractAccountTxnPb::new();
        txn.set_init(data);
        txn.set_gas_limit(gas);
        txn.set_gas_price(gas_price);
        txn.set_value(value);
        txn.set_nonce(nonce);
        SethTransaction::CreateContractAccount(txn)
    };

    let txn_signature = client.send_transaction(&from, txn).map_err(|error| {
        error!("{:?}", error);
        Error::internal_error()
    })?;

    Ok(hex_prefix(&txn_signature))
}

pub fn send_raw_transaction<T>(_params: Params, mut _client: ValidatorClient<T>) -> Result<Value, Error> where T: MessageSender {
    info!("eth_sendRawTransaction");
    // Implementing this requires substantial modification to the seth transaction family
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

pub fn get_transaction_receipt<T>(params: Params, mut client: ValidatorClient<T>) -> Result<Value, Error> where T: MessageSender {
    info!("eth_getTransactionReceipt");
    let txn_id: String = params.parse()
        .map_err(|_| Error::invalid_params("Takes [txnHash: DATA(64)]"))
        .and_then(|(v,): (String,)| v.get(2..)
            .map(|v| String::from(v))
            .ok_or_else(|| Error::invalid_params("Invalid transaction hash, must have 0x")))?;
    let receipt = match client.get_receipts(&[txn_id.clone()]) {
        Err(ClientError::NoResource) => {
            return Ok(Value::Null);
        },
        Ok(mut map) => match map.remove(&txn_id) {
            Some(r) => r,
            None => {
                error!("Receipt map is missing txn_id `{}`", txn_id);
                return Err(Error::internal_error());
            },
        },
        Err(error) => {
            error!("Error getting receipt for txn `{}`: {}", txn_id, error);
            return Err(Error::internal_error());
        },
    };
    let block = client.get_transaction_and_block(&TransactionKey::Signature(txn_id.clone()))
        .map_err(|error| {
            error!("Error getting block and transaction for txn `{}`: {}", txn_id, error);
            Error::internal_error()})
        .and_then(|(_, block_option)|
            block_option.ok_or_else(|| {
                error!("Txn `{}` had receipt but block was missing", txn_id);
                Error::internal_error()}))?;
    let block_header: BlockHeader = protobuf::parse_from_bytes(&block.header).map_err(|error| {
        error!("Error parsing block header: {}", error);
        Error::internal_error()
    })?;
    let index = block.get_batches().iter()
        .flat_map(|batch| batch.get_transactions().iter())
        .position(|txn| txn.header_signature == txn_id)
        .ok_or_else(|| {
            error!("Failed to find index of txn `{}` in block `{}`",
                txn_id, block.header_signature);
            Error::internal_error()})?;

    Ok(make_txn_receipt_obj(
        &receipt, index as u64, &block.header_signature, block_header.block_num))
}

pub fn gas_price<T>(_params: Params, mut _client: ValidatorClient<T>) -> Result<Value, Error> where T: MessageSender {
    info!("eth_gasPrice");
    Ok(Value::String(format!("{:#x}", 0)))
}

pub fn estimate_gas<T>(_params: Params, mut _client: ValidatorClient<T>) -> Result<Value, Error> where T: MessageSender {
    info!("eth_estimateGas");
    // Implementing this requires running the EVM, which is not possible within the RPC.
    Err(error::not_implemented())
}

pub fn sign<T>(params: Params, client: ValidatorClient<T>) -> Result<Value, Error> where T: MessageSender {
    info!("eth_sign");
    let (address, payload): (String, String) = params.parse()
        .map_err(|_| Error::invalid_params("Takes [txnHash: DATA(64)]"))?;
    let address = address.get(2..)
        .map(|a| String::from(a))
        .ok_or_else(|| Error::invalid_params("Address must have 0x prefix"))?;

    let payload = payload.get(2..)
        .ok_or_else(|| Error::invalid_params("Payload must have 0x prefix"))
        .and_then(|p| hex_str_to_bytes(&p).ok_or_else(||
            Error::invalid_params("Payload is invalid hex")))
        .and_then(|payload_data| {
            let payload_string = String::from_utf8(payload_data.clone()).map_err(|error|
                Error::invalid_params(format!("Payload is invalid utf8: {}", error)))?;
            let msg_string = format!(
                "\x19Ethereum Signed Message:\n{}{}", payload_data.len(), payload_string);
            let msg_data = msg_string.as_bytes();
            Ok(tiny_keccak::keccak256(&msg_data))
        })?;

    let account = client.loaded_accounts().iter()
        .find(|account| account.address() == address)
        .ok_or_else(||
            Error::invalid_params(format!("Account with address `{}` not found.", address)))?;

    let signature = account.sign(&payload).map_err(|error| {
        error!("Error signing payload: {}", error);
        Error::internal_error()
    })?;

    Ok(hex_prefix(&signature))
}

pub fn call<T>(_params: Params, mut _client: ValidatorClient<T>) -> Result<Value, Error> where T: MessageSender {
    info!("eth_estimateGas");
    // Implementing this requires running the EVM, which is not possible within the RPC.
    Err(error::not_implemented())
}

fn make_txn_receipt_obj(receipt: &SethReceipt, txn_idx: u64, block_id: &str, block_num: u64) -> Value {
    let mut map = Map::new();
    map.insert(String::from("transactionHash"), hex_prefix(&receipt.transaction_id));
    map.insert(String::from("transactionIndex"), num_to_hex(&txn_idx));
    map.insert(String::from("blockHash"), hex_prefix(block_id));
    map.insert(String::from("blockNumber"), num_to_hex(&block_num));
    map.insert(String::from("cumulativeGasUsed"), num_to_hex(&receipt.gas_used)); // Calculating this is expensive
    map.insert(String::from("gasUsed"), num_to_hex(&receipt.gas_used));
    map.insert(String::from("contractAddress"), hex_prefix(&receipt.contract_address));
    map.insert(String::from("logs"), Value::Array(receipt.logs.iter().map(|log|
        make_log_obj(log, &receipt.transaction_id, txn_idx, block_id, block_num)).collect()));
    Value::Object(map)
}

fn make_log_obj(log: &SethLog, txn_id: &str, txn_idx: u64, block_id: &str, block_num: u64) -> Value {
    let mut map = Map::new();
    map.insert(String::from("removed"), Value::Bool(false));
    map.insert(String::from("logIndex"), num_to_hex(&0)); // Calculating this is expensive
    map.insert(String::from("transactionIndex"), num_to_hex(&txn_idx));
    map.insert(String::from("transactionHash"), hex_prefix(txn_id));
    map.insert(String::from("blockHash"), hex_prefix(block_id));
    map.insert(String::from("blockNumber"), num_to_hex(&block_num));
    map.insert(String::from("address"), hex_prefix(&log.address));
    map.insert(String::from("data"), hex_prefix(&log.data));
    map.insert(String::from("topics"), Value::Array(log.topics.iter().map(|t|
        hex_prefix(t)).collect()));
    Value::Object(map)
}

fn make_txn_obj(txn: Transaction, txn_idx: u64, block_id: &str, block_num: u64) -> Value {
    let obj = make_txn_obj_no_block(txn);
    if let Value::Object(mut map) = obj {
        map.insert(String::from("blockHash"), hex_prefix(block_id));
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
