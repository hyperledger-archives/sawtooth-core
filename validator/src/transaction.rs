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

use proto;
use protobuf::{self, Message};

#[derive(Clone, Debug, PartialEq)]
pub struct Transaction {
    pub header_signature: String,
    pub payload: Vec<u8>,
    pub batcher_public_key: String,
    pub dependencies: Vec<String>,
    pub family_name: String,
    pub family_version: String,
    pub inputs: Vec<String>,
    pub outputs: Vec<String>,
    pub nonce: String,
    pub payload_sha512: String,
    pub signer_public_key: String,

    pub header_bytes: Vec<u8>,
}

impl From<Transaction> for proto::transaction::Transaction {
    fn from(other: Transaction) -> Self {
        let mut proto_transaction = proto::transaction::Transaction::new();
        proto_transaction.set_payload(other.payload);
        proto_transaction.set_header_signature(other.header_signature);
        proto_transaction.set_header(other.header_bytes);
        proto_transaction
    }
}

impl From<proto::transaction::Transaction> for Transaction {
    fn from(mut proto_txn: proto::transaction::Transaction) -> Self {
        let mut txn_header: proto::transaction::TransactionHeader =
            protobuf::parse_from_bytes(proto_txn.get_header())
                .expect("Unable to parse TransactionHeader bytes");

        Transaction {
            header_signature: proto_txn.take_header_signature(),
            header_bytes: proto_txn.take_header(),
            payload: proto_txn.take_payload(),
            batcher_public_key: txn_header.take_batcher_public_key(),
            dependencies: txn_header.take_dependencies().into_vec(),
            family_name: txn_header.take_family_name(),
            family_version: txn_header.take_family_version(),
            inputs: txn_header.take_inputs().into_vec(),
            outputs: txn_header.take_outputs().into_vec(),
            nonce: txn_header.take_nonce(),
            payload_sha512: txn_header.take_payload_sha512(),
            signer_public_key: txn_header.take_signer_public_key(),
        }
    }
}
