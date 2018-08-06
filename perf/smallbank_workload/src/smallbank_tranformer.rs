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

use crypto::digest::Digest;
use crypto::sha2::Sha512;
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

    fn get_dependencies_for_customer_ids(&self, customer_ids: &[u32]) -> Vec<String> {
        customer_ids
            .iter()
            .filter_map(|id| self.dependencies.get_signature(id))
            .map(|sig| sig.to_owned())
            .collect()
    }

    fn get_dependencies(&self, payload: &SmallbankTransactionPayload) -> Vec<String> {
        match payload.get_payload_type() {
            SmallbankTransactionPayload_PayloadType::DEPOSIT_CHECKING => self
                .get_dependencies_for_customer_ids(&[payload
                    .get_deposit_checking()
                    .get_customer_id()]),
            SmallbankTransactionPayload_PayloadType::WRITE_CHECK => self
                .get_dependencies_for_customer_ids(&[payload.get_write_check().get_customer_id()]),
            SmallbankTransactionPayload_PayloadType::TRANSACT_SAVINGS => self
                .get_dependencies_for_customer_ids(&[payload
                    .get_transact_savings()
                    .get_customer_id()]),
            SmallbankTransactionPayload_PayloadType::SEND_PAYMENT => self
                .get_dependencies_for_customer_ids(&[
                    payload.get_send_payment().get_source_customer_id(),
                    payload.get_send_payment().get_dest_customer_id(),
                ]),
            SmallbankTransactionPayload_PayloadType::AMALGAMATE => self
                .get_dependencies_for_customer_ids(&[
                    payload.get_amalgamate().get_source_customer_id(),
                    payload.get_amalgamate().get_dest_customer_id(),
                ]),
            _ => vec![],
        }
    }

    pub fn payload_to_transaction(
        &mut self,
        payload: &SmallbankTransactionPayload,
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

#[cfg(test)]
mod tests {
    use super::SBPayloadTransformer;

    use protobuf::Message;
    use sawtooth_sdk::messages::transaction::TransactionHeader;
    use sawtooth_sdk::signing;

    use playlist::SmallbankGeneratingIter;

    const NUM_CREATE_ACCOUNTS: usize = 100;
    const NUM_TO_CONSIDER: usize = 1_000;

    #[test]
    fn test_dependencies() {
        let seed = [84, 24, 24, 29, 98, 254, 76, 111, 198, 96, 211, 218, 238, 27];

        let payload_iterator = SmallbankGeneratingIter::new(NUM_CREATE_ACCOUNTS, &seed);

        let context = signing::create_context("secp256k1").unwrap();
        let private_key = context.new_random_private_key().unwrap();
        let signer = signing::Signer::new(context.as_ref(), private_key.as_ref());

        let mut transformer = SBPayloadTransformer::new(&signer);

        let mut transaction_iterator = payload_iterator
            .map(|payload| transformer.payload_to_transaction(&payload))
            .filter_map(|transaction| transaction.ok());

        let mut create_account_txn_ids = Vec::new();

        assert_eq!(
            transaction_iterator
                .by_ref()
                .take(NUM_CREATE_ACCOUNTS)
                .fold(0, |acc, transaction| {
                    create_account_txn_ids.push(transaction.header_signature.clone());

                    let header = header_from_bytes(transaction.get_header());
                    if header.dependencies.len() > 0 {
                        acc + 1
                    } else {
                        acc
                    }
                }),
            0
        );

        assert_eq!(
            transaction_iterator
                .take(NUM_TO_CONSIDER)
                .fold(0, |acc, transaction| {
                    let header = header_from_bytes(transaction.get_header());
                    assert!(header.get_dependencies().len() > 0);
                    if header
                        .get_dependencies()
                        .iter()
                        .any(|dep| !create_account_txn_ids.contains(&dep))
                    {
                        acc + 1
                    } else {
                        acc
                    }
                }),
            0
        );
    }

    fn header_from_bytes(header_bytes: &[u8]) -> TransactionHeader {
        let mut header = TransactionHeader::new();
        header.merge_from_bytes(header_bytes).unwrap();
        header
    }

}
