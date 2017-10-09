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
};
use transform;

use sawtooth_sdk::messages::block::BlockHeader;
use sawtooth_sdk::messaging::stream::MessageSender;
use error;
use requests::{RequestHandler};
use transactions::{TransactionKey, SethTransaction};

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

pub fn send_transaction<T>(params: Params, mut client: ValidatorClient<T>) -> Result<Value, Error> where T: MessageSender {
    info!("eth_sendTransaction");
    let (txn,): (Map<String, Value>,) = params.parse().map_err(|_|
        Error::invalid_params("Takes [txn: OBJECT]"))?;

    // Required arguments
    let from = transform::get_string_from_map(&txn, "from").and_then(|f| f.ok_or_else(||
        Error::invalid_params("`from` not set")))?;
    let data = transform::get_bytes_from_map(&txn, "data").and_then(|f| f.ok_or_else(||
        Error::invalid_params("`data` not set")))?;

    // Optional Arguments
    let to = transform::get_bytes_from_map(&txn, "to")?;
    let gas = transform::get_u64_from_map(&txn, "gas").map(|g| g.unwrap_or(90000))?;
    let gas_price = transform::get_u64_from_map(&txn, "gasPrice").map(|g| g.unwrap_or(10000000000000))?;
    let value = transform::get_u64_from_map(&txn, "value").map(|g| g.unwrap_or(0))?;
    let nonce = transform::get_u64_from_map(&txn, "nonce").map(|g| g.unwrap_or(0))?;

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

    Ok(transform::hex_prefix(&txn_signature))
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
                    Ok(transform::make_txn_obj(txn, index, &block.header_signature, block_header.block_num)),
                &TransactionKey::Signature(ref txn_id) => {
                    let txn_id = (*txn_id).clone();
                    let mut index = 0;
                    for mut batch in block.take_batches().into_iter() {
                        for transaction in batch.take_transactions().into_iter() {
                            if transaction.header_signature == txn_id {
                                return Ok(transform::make_txn_obj(
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
            Ok(transform::make_txn_obj_no_block(txn))
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

    Ok(transform::make_txn_receipt_obj(
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
        .and_then(|p| transform::hex_str_to_bytes(&p).ok_or_else(||
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

    Ok(transform::hex_prefix(&signature))
}

pub fn call<T>(_params: Params, mut _client: ValidatorClient<T>) -> Result<Value, Error> where T: MessageSender {
    info!("eth_estimateGas");
    // Implementing this requires running the EVM, which is not possible within the RPC.
    Err(error::not_implemented())
}
