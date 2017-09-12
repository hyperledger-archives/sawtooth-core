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

use sawtooth_sdk::messaging::zmq_stream::ZmqMessageSender;
use super::error;

pub fn new_filter(_params: Params, mut _sender: ZmqMessageSender) -> Result<Value, Error> {
    Err(error::not_implemented())
}
pub fn new_block_filter(_params: Params, mut _sender: ZmqMessageSender) -> Result<Value, Error> {
    Err(error::not_implemented())
}
pub fn new_pending_transaction_filter(_params: Params, mut _sender: ZmqMessageSender) -> Result<Value, Error> {
    Err(error::not_implemented())
}
pub fn uninstall_filter(_params: Params, mut _sender: ZmqMessageSender) -> Result<Value, Error> {
    Err(error::not_implemented())
}
pub fn get_filter_changes(_params: Params, mut _sender: ZmqMessageSender) -> Result<Value, Error> {
    Err(error::not_implemented())
}
pub fn get_filter_logs(_params: Params, mut _sender: ZmqMessageSender) -> Result<Value, Error> {
    Err(error::not_implemented())
}
pub fn get_logs(_params: Params, mut _sender: ZmqMessageSender) -> Result<Value, Error> {
    Err(error::not_implemented())
}
