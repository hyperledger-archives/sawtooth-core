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

use std::collections::HashMap;
use std::error::Error;

use cbor::GenericEncoder;

use crypto::digest::Digest;
use crypto::sha2::Sha512;

use protobuf::Message;
use protobuf::RepeatedField;

use rand::SeedableRng;
use rand::StdRng;
use rand::Rng;

use sawtooth_sdk::messages::transaction::Transaction;
use sawtooth_sdk::messages::transaction::TransactionHeader;
use sawtooth_sdk::signing;

use intkey_iterator::IntKeyPayload;
use intkey_addresser::IntKeyAddresser;

/// IntKeyTransformer a function (and associated state) used to transform
/// an IntKeyPayload into a Sawtooth Transaction.
pub struct IntKeyTransformer<'a> {
    unsatisfiable: f32,
    wildcard: f32,
    num_names: usize,
    signer: &'a signing::Signer<'a>,

    addresser: IntKeyAddresser,

    rng: StdRng,

    txn_id_by_name: HashMap<String, String>,
    txn_id_and_name: Vec<(String, String)>,
}

impl<'a> IntKeyTransformer<'a> {
    pub fn new(
        signer: &'a signing::Signer<'a>,
        seed: &[usize],
        unsatisfiable: f32,
        wildcard: f32,
        num_names: usize,
    ) -> IntKeyTransformer<'a> {
        IntKeyTransformer {
            unsatisfiable: unsatisfiable,
            wildcard: wildcard,
            num_names: num_names,
            signer: signer,
            rng: SeedableRng::from_seed(seed),
            addresser: IntKeyAddresser::new(),
            txn_id_by_name: HashMap::new(),
            txn_id_and_name: Vec::new(),
        }
    }

    fn payload_to_cbor_bytes(&mut self, payload: &IntKeyPayload) -> Result<Vec<u8>, Box<Error>> {
        let mut encoder = GenericEncoder::new(Vec::new());
        encoder.value(&payload.construct())?;
        Ok(encoder.into_inner().into_writer())
    }

    pub fn intkey_payload_to_transaction(
        &mut self,
        payload: IntKeyPayload,
    ) -> Result<Transaction, Box<Error>> {
        let mut txn = Transaction::new();
        let mut txn_header = TransactionHeader::new();

        txn_header.set_family_name(self.addresser.family_name.clone());
        txn_header.set_family_version(self.addresser.version.clone());

        txn_header.set_nonce(self.rng.gen_ascii_chars().take(50).collect());

        let payload_bytes = self.payload_to_cbor_bytes(&payload)?;

        let mut sha = Sha512::new();
        sha.input(payload_bytes.as_slice());

        txn_header.set_payload_sha512(sha.result_str());

        txn_header.set_signer_public_key(self.signer.get_public_key()?.as_hex());
        txn_header.set_batcher_public_key(self.signer.get_public_key()?.as_hex());

        let addresser = IntKeyAddresser::new();

        let addresses = RepeatedField::from_vec(vec![addresser.make_address(payload.name.clone())]);

        txn_header.set_inputs(addresses.clone());

        txn_header.set_outputs(addresses.clone());

        if payload.verb == "inc".to_string() || payload.verb == "dec".to_string() {
            match self.txn_id_by_name.get(&payload.name) {
                Some(txn_id) => {
                    let dependencies = RepeatedField::from_vec(vec![txn_id.clone().to_string()]);
                    txn_header.set_dependencies(dependencies);
                }
                None => {}
            }
        }
        if self.rng.gen_range(0.0, 1.0) < self.unsatisfiable {
            let random_bytes: Vec<u8> = self.rng.gen_iter::<u8>().take(100).collect();

            match self.signer.sign(random_bytes.as_slice()) {
                Ok(dep) => txn_header.dependencies.push(dep),
                Err(_) => (),
            }
        }

        let header_bytes = txn_header.write_to_bytes()?;

        let signature = self.signer.sign(&header_bytes.to_vec())?;

        if payload.verb == "set".to_string() {
            if !self.txn_id_by_name.contains_key(&payload.name) {
                self.txn_id_by_name
                    .insert(payload.name.clone(), signature.clone());
                self.txn_id_and_name
                    .push((payload.name.clone(), signature.clone()));
            }
            if self.txn_id_and_name.len() > self.num_names {
                let (name, _) = self.txn_id_and_name.remove(0);
                self.txn_id_by_name.remove(&name);
            }
        }

        txn.set_header(header_bytes);
        txn.set_header_signature(signature);
        txn.set_payload(payload_bytes);

        Ok(txn)
    }
}

#[cfg(test)]
mod tests {
    use super::IntKeyTransformer;

    use protobuf::Message;

    use sawtooth_sdk::messages::transaction::TransactionHeader;
    use sawtooth_sdk::signing;

    use intkey_iterator::IntKeyIterator;

    #[test]
    fn test_unsatisfiable() {
        let seed = [2, 3, 45, 95, 18, 81, 222, 2, 252, 2, 45];

        let intkey_iterator = IntKeyIterator::new(2, 0.0, &seed);

        let context = signing::create_context("secp256k1").unwrap();
        let private_key = context.new_random_private_key().unwrap();
        let signer = signing::Signer::new(context.as_ref(), private_key.as_ref());

        let mut transformer = IntKeyTransformer::new(&signer, &seed, 1.0, 0.0, 100);

        let transaction_iterator = intkey_iterator
            .map(|payload| transformer.intkey_payload_to_transaction(payload))
            .filter_map(|p| p.ok());

        let num_to_consider = 1_000;
        let mut transactions = Vec::new();
        assert!(
            transaction_iterator
                .take(num_to_consider)
                .fold(0, |acc, transaction| {
                    let sig = transaction.get_header_signature().to_string();
                    transactions.push(sig);
                    let mut header = TransactionHeader::new();
                    header
                        .merge_from_bytes(transaction.get_header())
                        .expect("Failed to deserialize header bytes");
                    if header
                        .get_dependencies()
                        .iter()
                        .any(|dep| !transactions.contains(&dep))
                    {
                        acc + 1
                    } else {
                        acc
                    }
                }) == num_to_consider
        );
    }

    #[test]
    fn test_all_satisfiable() {
        let seed = [2, 3, 45, 95, 18, 81, 222, 2, 252, 2, 45];

        let intkey_iterator = IntKeyIterator::new(2, 0.0, &seed);

        let context = signing::create_context("secp256k1").unwrap();
        let private_key = context.new_random_private_key().unwrap();
        let signer = signing::Signer::new(context.as_ref(), private_key.as_ref());

        let mut transformer = IntKeyTransformer::new(&signer, &seed, 0.0, 0.0, 100);

        let transaction_iterator = intkey_iterator
            .map(|payload| transformer.intkey_payload_to_transaction(payload))
            .filter_map(|p| p.ok());

        let num_to_consider = 1_000;
        let mut transactions = Vec::new();
        assert!(
            transaction_iterator
                .take(num_to_consider)
                .fold(0, |acc, transaction| {
                    let sig = transaction.get_header_signature().to_string();
                    transactions.push(sig);
                    let mut header = TransactionHeader::new();
                    header
                        .merge_from_bytes(transaction.get_header())
                        .expect("Failed to deserialize header bytes");
                    if header
                        .get_dependencies()
                        .iter()
                        .any(|dep| !transactions.contains(&dep))
                    {
                        acc + 1
                    } else {
                        acc
                    }
                }) == 0
        );
    }

}
