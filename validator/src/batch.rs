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

use transaction::Transaction;

#[derive(Clone, Debug, PartialEq)]
pub struct Batch {
    pub header_signature: String,
    pub transactions: Vec<Transaction>,
    pub signer_public_key: String,
    pub transaction_ids: Vec<String>,
    pub trace: bool,

    pub header_bytes: Vec<u8>,
}
