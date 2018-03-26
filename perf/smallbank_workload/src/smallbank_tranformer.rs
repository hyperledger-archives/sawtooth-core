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

use std::error::Error;
use std::time::Instant;

use crypto::sha2::Sha512;
use crypto::digest::Digest;
use protobuf;
use protobuf::Message;

use sawtooth_sdk::messages::transaction::{Transaction, TransactionHeader};
use sawtooth_sdk::signing;

use playlist::bytes_to_hex_str;
use playlist::make_addresses;
use smallbank::SmallbankTransactionPayload;

/// Transforms SmallbankTransactionPayloads into Sawtooth Transactions.
pub struct SBPayloadTransformer<'a> {
    signer: &'a signing::Signer<'a>,
}

impl<'a> SBPayloadTransformer<'a> {
    pub fn new(signer: &'a signing::Signer) -> Self {
        SBPayloadTransformer { signer: signer }
    }

    pub fn payload_to_transaction(
        &self,
        payload: SmallbankTransactionPayload,
    ) -> Result<Transaction, Box<Error>> {
        let mut txn = Transaction::new();
        let mut txn_header = TransactionHeader::new();

        txn_header.set_family_name(String::from("smallbank"));
        txn_header.set_family_version(String::from("1.0"));

        let elapsed = Instant::now().elapsed();
        txn_header.set_nonce(format!("{}{}", elapsed.as_secs(), elapsed.subsec_nanos()));

        let addresses = protobuf::RepeatedField::from_vec(make_addresses(&payload));

        txn_header.set_inputs(addresses.clone());
        txn_header.set_outputs(addresses.clone());

        let payload_bytes = payload.write_to_bytes()?;

        let mut sha = Sha512::new();
        sha.input(&payload_bytes);
        let hash: &mut [u8] = &mut [0; 64];
        sha.result(hash);

        txn_header.set_payload_sha512(bytes_to_hex_str(hash));
        txn_header.set_signer_public_key(self.signer.get_public_key()?.as_hex());
        txn_header.set_batcher_public_key(self.signer.get_public_key()?.as_hex());

        let header_bytes = txn_header.write_to_bytes()?;

        let signature = self.signer.sign(&header_bytes.to_vec())?;

        txn.set_header(header_bytes);
        txn.set_header_signature(signature);
        txn.set_payload(payload_bytes);

        Ok(txn)
    }
}
