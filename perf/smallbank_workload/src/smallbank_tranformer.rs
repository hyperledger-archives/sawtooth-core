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

use std::cmp::Eq;
use std::collections::HashMap;
use std::error::Error;
use std::hash::Hash;
use std::time::Instant;

use crypto::sha2::Sha512;
use crypto::digest::Digest;
use protobuf;
use protobuf::Message;

use sawtooth_sdk::messages::transaction::{Transaction, TransactionHeader};
use sawtooth_sdk::signing;

use playlist::bytes_to_hex_str;
use playlist::make_addresses;
use smallbank::{SmallbankTransactionPayload, SmallbankTransactionPayload_PayloadType};

/// Transforms SmallbankTransactionPayloads into Sawtooth Transactions.
pub struct SBPayloadTransformer<'a> {
    signer: &'a signing::Signer<'a>,
    dependencies: SignatureTracker<u32>,
}

impl<'a> SBPayloadTransformer<'a> {
    pub fn new(signer: &'a signing::Signer) -> Self {
        SBPayloadTransformer {
            signer: signer,
            dependencies: SignatureTracker::new(),
        }
    }

    fn add_signature_if_create_account(
        &mut self,
        payload: &SmallbankTransactionPayload,
        signature: String,
    ) {
        if payload.get_payload_type() == SmallbankTransactionPayload_PayloadType::CREATE_ACCOUNT {
            self.dependencies
                .add_signature(payload.get_create_account().get_customer_id(), signature);
        }
    }

    fn get_dependencies_for_customer_ids(&self, customer_ids: Vec<u32>) -> Vec<String> {
        customer_ids
            .iter()
            .filter_map(|id| self.dependencies.get_signature(id))
            .map(|sig| sig.to_owned())
            .collect()
    }

    fn get_dependencies(&self, payload: &SmallbankTransactionPayload) -> Vec<String> {
        match payload.get_payload_type() {
            SmallbankTransactionPayload_PayloadType::DEPOSIT_CHECKING => {
                self.get_dependencies_for_customer_ids(vec![
                    payload.get_deposit_checking().get_customer_id(),
                ])
            }
            SmallbankTransactionPayload_PayloadType::WRITE_CHECK => {
                self.get_dependencies_for_customer_ids(vec![
                    payload.get_write_check().get_customer_id(),
                ])
            }
            SmallbankTransactionPayload_PayloadType::TRANSACT_SAVINGS => {
                self.get_dependencies_for_customer_ids(vec![
                    payload.get_transact_savings().get_customer_id(),
                ])
            }
            SmallbankTransactionPayload_PayloadType::SEND_PAYMENT => {
                self.get_dependencies_for_customer_ids(vec![
                    payload.get_send_payment().get_source_customer_id(),
                    payload.get_send_payment().get_dest_customer_id(),
                ])
            }
            SmallbankTransactionPayload_PayloadType::AMALGAMATE => {
                self.get_dependencies_for_customer_ids(vec![
                    payload.get_amalgamate().get_source_customer_id(),
                    payload.get_amalgamate().get_dest_customer_id(),
                ])
            }
            _ => vec![],
        }
    }

    pub fn payload_to_transaction(
        &mut self,
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

        let dependencies = protobuf::RepeatedField::from_vec(self.get_dependencies(&payload));
        txn_header.set_dependencies(dependencies);

        let payload_bytes = payload.clone().write_to_bytes()?;

        let mut sha = Sha512::new();
        sha.input(&payload_bytes);
        let hash: &mut [u8] = &mut [0; 64];
        sha.result(hash);

        txn_header.set_payload_sha512(bytes_to_hex_str(hash));
        txn_header.set_signer_public_key(self.signer.get_public_key()?.as_hex());
        txn_header.set_batcher_public_key(self.signer.get_public_key()?.as_hex());

        let header_bytes = txn_header.write_to_bytes()?;

        let signature = self.signer.sign(&header_bytes.to_vec())?;
        self.add_signature_if_create_account(&payload, signature.clone());

        txn.set_header(header_bytes);
        txn.set_header_signature(signature);
        txn.set_payload(payload_bytes);

        Ok(txn)
    }
}

struct SignatureTracker<T>
where
    T: Eq + Hash,
{
    signature_by_id: HashMap<T, String>,
}

impl<T> SignatureTracker<T>
where
    T: Eq + Hash,
{
    pub fn new() -> SignatureTracker<T> {
        SignatureTracker {
            signature_by_id: HashMap::new(),
        }
    }

    pub fn get_signature(&self, id: &T) -> Option<&String> {
        self.signature_by_id.get(id)
    }

    pub fn add_signature(&mut self, id: T, signature: String) {
        self.signature_by_id.insert(id, signature);
    }
}

