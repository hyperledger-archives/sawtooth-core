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

impl From<Batch> for proto::batch::Batch {
    fn from(batch: Batch) -> Self {
        let mut proto_batch = proto::batch::Batch::new();
        proto_batch.set_transactions(protobuf::RepeatedField::from_vec(
            batch
                .transactions
                .into_iter()
                .map(proto::transaction::Transaction::from)
                .collect(),
        ));
        proto_batch.set_header_signature(batch.header_signature);
        proto_batch.set_header(batch.header_bytes);
        proto_batch
    }
}

impl From<proto::batch::Batch> for Batch {
    fn from(mut proto_batch: proto::batch::Batch) -> Batch {
        let mut batch_header: proto::batch::BatchHeader =
            protobuf::parse_from_bytes(proto_batch.get_header())
                .expect("Unable to parse BatchHeader bytes");

        Batch {
            header_signature: proto_batch.take_header_signature(),
            header_bytes: proto_batch.take_header(),
            signer_public_key: batch_header.take_signer_public_key(),
            transaction_ids: batch_header.take_transaction_ids().into_vec(),
            trace: proto_batch.get_trace(),

            transactions: proto_batch
                .take_transactions()
                .into_iter()
                .map(Transaction::from)
                .collect(),
        }
    }
}
