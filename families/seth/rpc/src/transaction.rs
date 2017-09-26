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

use super::requests::{ValidatorClient};

use sawtooth_sdk::messaging::stream::MessageSender;
use super::error;

pub fn get_transaction_count<T>(_params: Params, mut _client: ValidatorClient<T>) -> Result<Value, Error> where T: MessageSender {
    Err(error::not_implemented())
}
pub fn get_block_transaction_count_by_hash<T>(_params: Params, mut _client: ValidatorClient<T>) -> Result<Value, Error> where T: MessageSender {
    Err(error::not_implemented())
}
pub fn get_block_transaction_count_by_number<T>(_params: Params, mut _client: ValidatorClient<T>) -> Result<Value, Error> where T: MessageSender {
    Err(error::not_implemented())
}
pub fn send_transaction<T>(_params: Params, mut _client: ValidatorClient<T>) -> Result<Value, Error> where T: MessageSender {
    Err(error::not_implemented())
}
pub fn send_raw_transaction<T>(_params: Params, mut _client: ValidatorClient<T>) -> Result<Value, Error> where T: MessageSender {
    Err(error::not_implemented())
}
pub fn get_transaction_by_hash<T>(_params: Params, mut _client: ValidatorClient<T>) -> Result<Value, Error> where T: MessageSender {
    Err(error::not_implemented())
}
pub fn get_transaction_by_block_hash_and_index<T>(_params: Params, mut _client: ValidatorClient<T>) -> Result<Value, Error> where T: MessageSender {
    Err(error::not_implemented())
}
pub fn get_transaction_by_block_number_and_index<T>(_params: Params, mut _client: ValidatorClient<T>) -> Result<Value, Error> where T: MessageSender {
    Err(error::not_implemented())
}
pub fn get_transaction_receipt<T>(_params: Params, mut _client: ValidatorClient<T>) -> Result<Value, Error> where T: MessageSender {
    Err(error::not_implemented())
}
pub fn gas_price<T>(_params: Params, mut _client: ValidatorClient<T>) -> Result<Value, Error> where T: MessageSender {
    Err(error::not_implemented())
}
pub fn estimate_gas<T>(_params: Params, mut _client: ValidatorClient<T>) -> Result<Value, Error> where T: MessageSender {
    Err(error::not_implemented())
}
