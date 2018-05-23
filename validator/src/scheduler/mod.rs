/*
 * Copyright 2018 Intel Corporation
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

use proto::events::Event;
use proto::transaction_receipt::StateChange;

mod execution_result_ffi;

pub use self::execution_result_ffi::{BatchResult, TransactionResult};

pub struct ExecutionResults {
    pub beginning_state_hash: Option<String>,
    pub ending_state_hash: Option<String>,
    pub batch_results: Vec<(String, Vec<TxnExecutionResult>)>,
}

pub struct TxnExecutionResult {
    pub signature: String,
    pub is_valid: bool,
    pub state_changes: Vec<StateChange>,
    pub events: Vec<Event>,
    pub data: Vec<(String, Vec<u8>)>,
    pub error_message: String,
    pub error_data: Vec<u8>,
}
