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


use jsonrpc_core::{Value, Error};
use serde_json::Map;
use std::fmt::{LowerHex};
use transactions::{Transaction, SethReceipt, SethLog};

// -- Hex --

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

// -- To/From Value

// -- String --
pub fn num_to_hex<T>(n: &T) -> Value where T: LowerHex {
    Value::String(String::from(format!("{:#x}", n)))
}

pub fn hex_prefix(s: &str) -> Value {
    Value::String(String::from(format!("0x{}", s)))
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

pub fn from_hex_value_then<T, F>(value: &Value, then: F) -> Result<T, Error>
    where F: FnOnce(&str) -> Result<T, Error>
{
    value.as_str()
        .ok_or_else(|| Error::invalid_params(format!("Not a string")))
        .and_then(|v| v.get(2..).ok_or_else(||
            Error::invalid_params(format!("Must have 0x"))))
        .and_then(then)
}

pub fn u64_from_hex_value(value: &Value) -> Result<u64, Error> {
    from_hex_value_then(value, |s|
        u64::from_str_radix(s, 16).map_err(|error|
            Error::invalid_params(format!("Not a number: {:?}", error))))
}

pub fn bytes_from_hex_value(value: &Value) -> Result<Vec<u8>, Error> {
    from_hex_value_then(value, |s|
        hex_str_to_bytes(s).ok_or_else(||
                Error::invalid_params(format!("Not valid hex", ))))
}

pub fn string_from_hex_value(value: &Value) -> Result<String, Error> {
    from_hex_value_then(value, |s| Ok(String::from(s)))
}

// -- Map -- //
pub fn get_hex_value_from_map_then<F,T>(map: &Map<String, Value>, key: &str, then: F) -> Result<Option<T>, Error>
    where F: FnOnce(&Value) -> Result<T, Error>
{
    if let Some(value) = map.get(key) {
        then(value).map(|v| Some(v))
    } else {
        Ok(None)
    }
}

pub fn get_u64_from_map(map: &Map<String, Value>, key: &str) -> Result<Option<u64>, Error> {
    get_hex_value_from_map_then(map, key, u64_from_hex_value)
}

pub fn get_bytes_from_map(map: &Map<String, Value>, key: &str) -> Result<Option<Vec<u8>>, Error> {
    get_hex_value_from_map_then(map, key, bytes_from_hex_value)
}

pub fn get_string_from_map(map: &Map<String, Value>, key: &str) -> Result<Option<String>, Error> {
    get_hex_value_from_map_then(map, key, string_from_hex_value)
}

// -- Array -- //
pub fn get_array_from_map(map: &Map<String, Value>, key: &str) -> Result<Vec<Value>, Error> {
    if let Some(value) = map.get(key) {
        value.as_array()
            .ok_or_else(|| Error::invalid_params(format!("Not an array")))
            .map(|a| a.clone())
    } else {
        Ok(Vec::new())
    }
}

// -- Receipt --
pub fn make_txn_receipt_obj(receipt: &SethReceipt, txn_idx: u64, block_id: &str, block_num: u64) -> Value {
    let mut map = Map::new();
    map.insert(String::from("transactionHash"), hex_prefix(&receipt.transaction_id));
    map.insert(String::from("transactionIndex"), num_to_hex(&txn_idx));
    map.insert(String::from("blockHash"), hex_prefix(block_id));
    map.insert(String::from("blockNumber"), num_to_hex(&block_num));
    map.insert(String::from("cumulativeGasUsed"), num_to_hex(&receipt.gas_used)); // Calculating this is expensive
    map.insert(String::from("gasUsed"), num_to_hex(&receipt.gas_used));
    map.insert(String::from("contractAddress"), hex_prefix(&receipt.contract_address));
    map.insert(String::from("returnValue"), hex_prefix(&receipt.return_value));
    map.insert(String::from("logs"), Value::Array(receipt.logs.iter().map(|log|
        make_log_obj(log, &receipt.transaction_id, txn_idx, block_id, block_num)).collect()));
    Value::Object(map)
}

// -- Log --
pub fn make_log_obj(log: &SethLog, txn_id: &str, txn_idx: u64, block_id: &str, block_num: u64) -> Value {
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

// -- Transaction --
pub fn make_txn_obj(txn: Transaction, txn_idx: u64, block_id: &str, block_num: u64) -> Value {
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

pub fn make_txn_obj_no_block(txn: Transaction) -> Value {
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
