// Copyright 2018 Bitwise IO, Inc.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

use crypto::digest::Digest;
use crypto::sha2::Sha512;
use failure::{Backtrace, Context, Fail};
use protobuf::{Message, ProtobufError, RepeatedField};
use sawtooth_sdk::messages::batch::{Batch, BatchHeader, BatchList};
use sawtooth_sdk::messages::transaction::{Transaction, TransactionHeader};
use sawtooth_sdk::signing::{Error as SigningError, Signer};
use std::fmt;
use std::time::{SystemTime, UNIX_EPOCH};

#[derive(Debug)]
pub struct Error {
    inner: Context<ErrorKind>,
}

#[derive(Clone, Eq, PartialEq, Debug, Fail)]
pub enum ErrorKind {
    #[fail(display = "Missing information: {}", _0)]
    MissingInfo(String),

    #[fail(display = "{}", _0)]
    SigningError(String),

    #[fail(display = "{}", _0)]
    SerializationError(String),
}

impl Fail for Error {
    fn cause(&self) -> Option<&dyn Fail> {
        self.inner.cause()
    }

    fn backtrace(&self) -> Option<&Backtrace> {
        self.inner.backtrace()
    }
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        fmt::Display::fmt(&self.inner, f)
    }
}

impl Error {
    pub fn kind(&self) -> ErrorKind {
        self.inner.get_context().clone()
    }
}

impl From<ErrorKind> for Error {
    fn from(kind: ErrorKind) -> Self {
        Error {
            inner: Context::new(kind),
        }
    }
}

impl From<Context<ErrorKind>> for Error {
    fn from(inner: Context<ErrorKind>) -> Self {
        Error { inner }
    }
}

impl From<SigningError> for Error {
    fn from(err: SigningError) -> Self {
        Error {
            inner: Context::new(ErrorKind::SigningError(format!("{}", err))),
        }
    }
}

impl From<ProtobufError> for Error {
    fn from(err: ProtobufError) -> Self {
        Error {
            inner: Context::new(ErrorKind::SerializationError(format!("{}", err))),
        }
    }
}

#[derive(Clone, Default)]
pub struct TransactionBuilder<'a> {
    family_name: Option<String>,
    family_version: Option<String>,
    inputs: Option<Vec<String>>,
    nonce: Option<u64>,
    outputs: Option<Vec<String>>,
    payload: Option<Vec<u8>>,
    signer: Option<&'a Signer<'a>>,
}

impl<'a> TransactionBuilder<'a> {
    pub fn new() -> Self {
        Self {
            ..Default::default()
        }
    }

    pub fn family_name<S: Into<String>>(mut self, name: S) -> Self {
        self.family_name = Some(name.into());
        self
    }

    pub fn family_version<S: Into<String>>(mut self, version: S) -> Self {
        self.family_version = Some(version.into());
        self
    }

    pub fn nonce(mut self, nonce: u64) -> Self {
        self.nonce = Some(nonce);
        self
    }

    pub fn input<S: Into<String>>(mut self, input: S) -> Self {
        self.inputs.get_or_insert_with(Vec::new).push(input.into());
        self
    }

    pub fn inputs<S: Into<String>>(mut self, inputs: Vec<S>) -> Self {
        self.inputs
            .get_or_insert_with(Vec::new)
            .extend(inputs.into_iter().map(|i| i.into()));
        self
    }

    pub fn output<S: Into<String>>(mut self, output: S) -> Self {
        self.outputs
            .get_or_insert_with(Vec::new)
            .push(output.into());
        self
    }

    pub fn outputs<S: Into<String>>(mut self, outputs: Vec<S>) -> Self {
        self.outputs
            .get_or_insert_with(Vec::new)
            .extend(outputs.into_iter().map(|o| o.into()));
        self
    }

    pub fn addresses<S: Into<String>>(mut self, addresses: Vec<S>) -> Self {
        let addrs: Vec<String> = addresses.into_iter().map(|a| a.into()).collect();
        self.inputs
            .get_or_insert_with(Vec::new)
            .extend(addrs.clone());
        self.outputs.get_or_insert_with(Vec::new).extend(addrs);
        self
    }

    pub fn payload(mut self, payload: Vec<u8>) -> Self {
        self.payload = Some(payload);
        self
    }

    pub fn signer(mut self, signer: &'a Signer<'a>) -> Self {
        self.signer = Some(signer);
        self
    }

    pub fn build(self) -> Result<(Transaction, TransactionHeader), Error> {
        let mut txn = Transaction::new();
        let mut txn_header = TransactionHeader::new();

        let payload = self
            .payload
            .ok_or_else(|| ErrorKind::MissingInfo("Payload".into()))?;
        let signer = self
            .signer
            .ok_or_else(|| ErrorKind::MissingInfo("Signer".into()))?;
        let family_name = &self
            .family_name
            .ok_or_else(|| ErrorKind::MissingInfo("Family Name".into()))?;
        let family_version = &self
            .family_version
            .ok_or_else(|| ErrorKind::MissingInfo("Family Version".into()))?;

        let default_nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("Time went backwards!")
            .as_secs();

        txn_header.set_family_name(family_name.clone());
        txn_header.set_family_version(family_version.clone());
        txn_header.set_nonce(self.nonce.unwrap_or(default_nonce).to_string());
        txn_header.set_signer_public_key(signer.get_public_key()?.as_hex());

        txn_header.set_inputs(RepeatedField::from_vec(
            self.inputs.unwrap_or_else(Vec::new),
        ));
        txn_header.set_outputs(RepeatedField::from_vec(
            self.outputs.unwrap_or_else(Vec::new),
        ));

        let mut sha = Sha512::new();
        sha.input(&payload);
        let hash: &mut [u8] = &mut [0; 64];
        sha.result(hash);
        txn_header.set_payload_sha512(
            hash.iter()
                .map(|b| format!("{:02x}", b))
                .collect::<Vec<_>>()
                .join(""),
        );

        txn.set_payload(payload.clone());

        Ok((txn, txn_header))
    }

    pub fn build_batch(self) -> Result<Batch, Error> {
        let signer = self
            .signer
            .ok_or_else(|| ErrorKind::MissingInfo("Signer".into()))?;
        BatchBuilder::new().signer(signer).transaction(self).build()
    }

    pub fn build_batch_list(self) -> Result<BatchList, Error> {
        let signer = self
            .signer
            .ok_or_else(|| ErrorKind::MissingInfo("Signer".into()))?;
        BatchListBuilder::new()
            .batch(BatchBuilder::new().signer(signer).transaction(self))
            .build()
    }

    pub fn build_request_bytes(self) -> Result<Vec<u8>, Error> {
        let signer = self
            .signer
            .ok_or_else(|| ErrorKind::MissingInfo("Signer".into()))?;
        Ok(BatchListBuilder::new()
            .batch(BatchBuilder::new().signer(signer).transaction(self))
            .build()?
            .write_to_bytes()?)
    }
}

#[derive(Clone, Default)]
pub struct BatchBuilder<'a> {
    signer: Option<&'a Signer<'a>>,
    transactions: Option<Vec<TransactionBuilder<'a>>>,
}

impl<'a> BatchBuilder<'a> {
    pub fn new() -> Self {
        Self {
            ..Default::default()
        }
    }

    pub fn signer(mut self, signer: &'a Signer<'a>) -> Self {
        self.signer = Some(signer);
        self
    }

    pub fn transaction(mut self, transaction: TransactionBuilder<'a>) -> Self {
        self.transactions
            .get_or_insert_with(Vec::new)
            .push(transaction);
        self
    }

    pub fn transactions(mut self, transactions: Vec<TransactionBuilder<'a>>) -> Self {
        self.transactions
            .get_or_insert_with(Vec::new)
            .extend(transactions);
        self
    }

    pub fn build(self) -> Result<Batch, Error> {
        let signer = self
            .signer
            .ok_or_else(|| ErrorKind::MissingInfo("Signer".into()))?;
        let transactions = self
            .transactions
            .ok_or_else(|| ErrorKind::MissingInfo("Transactions".into()))?;
        let mut built_transactions = vec![];

        for txn_builder in transactions {
            let (mut txn, mut header) = txn_builder.build()?;
            header.set_batcher_public_key(signer.get_public_key()?.as_hex());

            let header_bytes = header.write_to_bytes()?;
            txn.set_header(header_bytes.clone());

            let b: &[u8] = &header_bytes;
            txn.set_header_signature(signer.sign(b)?);

            built_transactions.push(txn);
        }

        let mut batch = Batch::new();
        let mut batch_header = BatchHeader::new();

        batch_header.set_transaction_ids(RepeatedField::from_vec(
            built_transactions
                .iter()
                .map(|t| t.header_signature.clone())
                .collect(),
        ));
        batch_header.set_signer_public_key(signer.get_public_key()?.as_hex());
        batch.set_transactions(RepeatedField::from_vec(built_transactions));

        let batch_header_bytes = batch_header.write_to_bytes()?;
        batch.set_header(batch_header_bytes.clone());

        let b: &[u8] = &batch_header_bytes;
        batch.set_header_signature(signer.sign(b)?);

        Ok(batch)
    }

    pub fn build_batch_list(self) -> Result<BatchList, Error> {
        BatchListBuilder::new().batch(self).build()
    }

    pub fn build_request_bytes(self) -> Result<Vec<u8>, Error> {
        Ok(BatchListBuilder::new()
            .batch(self)
            .build()?
            .write_to_bytes()?)
    }
}

#[derive(Clone, Default)]
pub struct BatchListBuilder<'a> {
    batches: Option<Vec<BatchBuilder<'a>>>,
}

impl<'a> BatchListBuilder<'a> {
    pub fn new() -> Self {
        Self {
            ..Default::default()
        }
    }

    pub fn batch(mut self, batch: BatchBuilder<'a>) -> Self {
        self.batches.get_or_insert_with(Vec::new).push(batch);
        self
    }

    pub fn batches(mut self, batches: Vec<BatchBuilder<'a>>) -> Self {
        self.batches.get_or_insert_with(Vec::new).extend(batches);
        self
    }

    pub fn build(self) -> Result<BatchList, Error> {
        let batches = self
            .batches
            .ok_or_else(|| ErrorKind::MissingInfo("Batches".into()))?;

        let mut built_batches = vec![];

        for batch in batches {
            built_batches.push(batch.build()?);
        }

        let mut batch_list = BatchList::new();
        batch_list.set_batches(RepeatedField::from_vec(built_batches));

        Ok(batch_list)
    }

    pub fn build_request_bytes(self) -> Result<Vec<u8>, Error> {
        Ok(self.build()?.write_to_bytes()?)
    }
}

#[cfg(test)]
mod tests {
    use super::{BatchBuilder, BatchListBuilder, TransactionBuilder};
    use sawtooth_sdk::signing::secp256k1::Secp256k1PrivateKey;
    use sawtooth_sdk::signing::{create_context, Signer};

    fn get_key() -> Secp256k1PrivateKey {
        Secp256k1PrivateKey::from_hex(
            "64660c5faa745c24df472be178113a6441fa2fe53a59786289ba635d5dc085dc",
        )
        .unwrap()
    }

    #[test]
    fn single_transaction() {
        let context = create_context("secp256k1").unwrap();
        let key = get_key();
        let signer = Signer::new(&*context, &key);

        let batch_list = TransactionBuilder::new()
            .family_name("foo")
            .family_version("1.0")
            .inputs(vec!["000000", "000001"])
            .outputs(vec!["000001", "000002"])
            .payload(vec![1, 2, 3])
            .signer(&signer)
            .build_batch_list()
            .unwrap();

        assert_eq!(batch_list.batches.len(), 1);

        for batch in &batch_list.batches {
            assert_eq!(batch.transactions.len(), 1);
            assert_eq!(batch.header.len(), 199);
            assert_eq!(batch.header_signature.len(), 128);

            for transaction in &batch.transactions {
                assert_eq!(transaction.header.len(), 321);
                assert_eq!(transaction.header_signature.len(), 128);
                assert_eq!(transaction.payload, vec![1u8, 2, 3]);
            }
        }
    }

    #[test]
    fn multiple_transactions() {
        let context = create_context("secp256k1").unwrap();
        let key = get_key();
        let signer = Signer::new(&*context, &key);

        let batch_list = BatchBuilder::new()
            .signer(&signer)
            .transactions(vec![
                TransactionBuilder::new()
                    .family_name("foo")
                    .family_version("1.0")
                    .inputs(vec!["000000", "000001"])
                    .outputs(vec!["000001", "000002"])
                    .payload(vec![1, 2, 3])
                    .signer(&signer),
                TransactionBuilder::new()
                    .family_name("foo")
                    .family_version("1.0")
                    .addresses(vec!["000002", "000003"])
                    .payload(vec![4, 5, 6])
                    .signer(&signer),
            ])
            .build_batch_list()
            .unwrap();

        assert_eq!(batch_list.batches.len(), 1);

        for batch in &batch_list.batches {
            assert_eq!(batch.transactions.len(), 2);
            assert_eq!(batch.header.len(), 330);
            assert_eq!(batch.header_signature.len(), 128);

            for (i, transaction) in batch.transactions.iter().enumerate() {
                assert_eq!(transaction.header.len(), 321);
                assert_eq!(transaction.header_signature.len(), 128);
                assert_eq!(
                    transaction.payload,
                    match i {
                        0 => vec![1u8, 2, 3],
                        _ => vec![4u8, 5, 6],
                    }
                );
            }
        }
    }

    #[test]
    fn multiple_batches() {
        let context = create_context("secp256k1").unwrap();
        let key = get_key();
        let signer = Signer::new(&*context, &key);

        let batch_list = BatchListBuilder::new()
            .batches(vec![
                BatchBuilder::new()
                    .signer(&signer)
                    .transactions(vec![TransactionBuilder::new()
                        .family_name("foo")
                        .family_version("1.0")
                        .addresses(vec!["000000"])
                        .payload(vec![1, 2, 3])
                        .signer(&signer)]),
                BatchBuilder::new()
                    .signer(&signer)
                    .transactions(vec![TransactionBuilder::new()
                        .family_name("foo")
                        .family_version("1.0")
                        .addresses(vec!["000000"])
                        .payload(vec![4, 5, 6])
                        .signer(&signer)]),
            ])
            .build()
            .unwrap();

        assert_eq!(batch_list.batches.len(), 2);

        for (i, batch) in batch_list.batches.iter().enumerate() {
            assert_eq!(batch.transactions.len(), 1);
            assert_eq!(batch.header.len(), 199);
            assert_eq!(batch.header_signature.len(), 128);

            for transaction in &batch.transactions {
                assert_eq!(transaction.header.len(), 305);
                assert_eq!(transaction.header_signature.len(), 128);
                assert_eq!(
                    transaction.payload,
                    match i {
                        0 => vec![1u8, 2, 3],
                        _ => vec![4u8, 5, 6],
                    }
                );
            }
        }
    }
}
