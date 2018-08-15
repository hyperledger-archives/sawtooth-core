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

//! Tools for generating signed batches from a stream of transactions

extern crate protobuf;

use std::error;
use std::fmt;
use std::io::Read;
use std::io::Write;

use self::protobuf::Message;
use sawtooth_sdk::messages::batch::Batch;
use sawtooth_sdk::messages::batch::BatchHeader;
use sawtooth_sdk::messages::transaction::Transaction;

use sawtooth_sdk::signing;

use source::LengthDelimitedMessageSource;

/// Generates signed batches from a stream of length-delimited transactions.
/// Constrains the batches to `max_batch_size` number of transactions per
/// batch.  The resulting batches are written in a length-delimited fashion to
/// the given writer.
pub fn generate_signed_batches<'a>(
    reader: &'a mut Read,
    writer: &'a mut Write,
    max_batch_size: usize,
    signing_context: &signing::Context,
    signing_key: &signing::PrivateKey,
) -> Result<(), BatchingError> {
    let crypto_factory = signing::CryptoFactory::new(signing_context);
    let signer = crypto_factory.new_signer(signing_key);

    let mut producer = SignedBatchProducer::new(reader, max_batch_size, &signer);
    loop {
        match producer.next() {
            Some(Ok(batch)) => {
                if let Err(err) = batch.write_length_delimited_to_writer(writer) {
                    return Err(BatchingError::MessageError(err));
                }
            }
            None => break,
            Some(Err(err)) => return Err(err),
        }
    }

    Ok(())
}

type TransactionSource<'a> = LengthDelimitedMessageSource<'a, Transaction>;

/// Errors that may occur during the generation of batches.
#[derive(Debug)]
pub enum BatchingError {
    MessageError(protobuf::ProtobufError),
    SigningError(signing::Error),
}

impl From<signing::Error> for BatchingError {
    fn from(err: signing::Error) -> Self {
        BatchingError::SigningError(err)
    }
}

impl From<protobuf::ProtobufError> for BatchingError {
    fn from(err: protobuf::ProtobufError) -> Self {
        BatchingError::MessageError(err)
    }
}

impl fmt::Display for BatchingError {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match *self {
            BatchingError::MessageError(ref err) => {
                write!(f, "Error occurred reading messages: {}", err)
            }
            BatchingError::SigningError(ref err) => write!(f, "Unable to sign batch: {}", err),
        }
    }
}

impl error::Error for BatchingError {
    fn description(&self) -> &str {
        match *self {
            BatchingError::MessageError(ref err) => err.description(),
            BatchingError::SigningError(ref err) => err.description(),
        }
    }

    fn cause(&self) -> Option<&error::Error> {
        match *self {
            BatchingError::MessageError(ref err) => Some(err),
            BatchingError::SigningError(ref err) => Some(err),
        }
    }
}

/// Produces signed batches from a length-delimited source of Transactions.
pub struct SignedBatchProducer<'a> {
    transaction_source: TransactionSource<'a>,
    max_batch_size: usize,
    signer: &'a signing::Signer<'a>,
}

/// Resulting batch or error.
pub type BatchResult = Result<Batch, BatchingError>;

impl<'a> SignedBatchProducer<'a> {
    /// Creates a new `SignedBatchProducer` with a given Transaction source and
    /// a max number of transactions per batch.
    pub fn new(source: &'a mut Read, max_batch_size: usize, signer: &'a signing::Signer) -> Self {
        let transaction_source = LengthDelimitedMessageSource::new(source);
        SignedBatchProducer {
            transaction_source,
            max_batch_size,
            signer,
        }
    }
}

impl<'a> Iterator for SignedBatchProducer<'a> {
    type Item = BatchResult;

    /// Gets the next BatchResult.
    /// `Ok(None)` indicates that the underlying source has been consumed.
    fn next(&mut self) -> Option<BatchResult> {
        let txns = match self.transaction_source.next(self.max_batch_size) {
            Ok(txns) => txns,
            Err(err) => return Some(Err(BatchingError::MessageError(err))),
        };
        if txns.is_empty() {
            None
        } else {
            Some(batch_transactions(txns, self.signer))
        }
    }
}

fn batch_transactions(txns: Vec<Transaction>, signer: &signing::Signer) -> BatchResult {
    let mut batch_header = BatchHeader::new();

    // set signer_public_key
    let pk = match signer.get_public_key() {
        Ok(pk) => pk,
        Err(err) => return Err(BatchingError::SigningError(err)),
    };
    let public_key = pk.as_hex();

    let txn_ids = txns
        .iter()
        .map(|txn| String::from(txn.get_header_signature()))
        .collect();
    batch_header.set_transaction_ids(protobuf::RepeatedField::from_vec(txn_ids));
    batch_header.set_signer_public_key(public_key);

    let header_bytes = batch_header.write_to_bytes()?;
    let signature = signer
        .sign(&header_bytes)
        .map_err(BatchingError::SigningError);
    match signature {
        Ok(signature) => {
            let mut batch = Batch::new();
            batch.set_header_signature(signature);
            batch.set_header(header_bytes);
            batch.set_transactions(protobuf::RepeatedField::from_vec(txns));

            Ok(batch)
        }
        Err(err) => Err(err),
    }
}

pub struct SignedBatchIterator<'a> {
    transaction_iterator: &'a mut Iterator<Item = Transaction>,
    max_batch_size: usize,
    signer: &'a signing::Signer<'a>,
}

impl<'a> SignedBatchIterator<'a> {
    pub fn new(
        iterator: &'a mut Iterator<Item = Transaction>,
        max_batch_size: usize,
        signer: &'a signing::Signer,
    ) -> Self {
        SignedBatchIterator {
            transaction_iterator: iterator,
            max_batch_size,
            signer,
        }
    }
}

impl<'a> Iterator for SignedBatchIterator<'a> {
    type Item = BatchResult;

    fn next(&mut self) -> Option<Self::Item> {
        let txns = self
            .transaction_iterator
            .take(self.max_batch_size)
            .collect();

        Some(batch_transactions(txns, self.signer))
    }
}

#[cfg(test)]
mod tests {
    use super::protobuf;
    use super::protobuf::Message;
    use super::LengthDelimitedMessageSource;
    use super::SignedBatchProducer;
    use super::TransactionSource;
    use sawtooth_sdk::messages::batch::{Batch, BatchHeader};
    use sawtooth_sdk::messages::transaction::{Transaction, TransactionHeader};
    use sawtooth_sdk::signing;
    use std::io::{Cursor, Write};

    type BatchSource<'a> = LengthDelimitedMessageSource<'a, Batch>;

    #[test]
    fn empty_transaction_source() {
        let encoded_bytes: Vec<u8> = Vec::new();
        let mut source = Cursor::new(encoded_bytes);

        let mut txn_stream: TransactionSource = LengthDelimitedMessageSource::new(&mut source);
        let txns = txn_stream.next(2).unwrap();
        assert_eq!(txns.len(), 0);
    }

    #[test]
    fn next_transactions() {
        let mut encoded_bytes: Vec<u8> = Vec::new();

        write_txn_with_sig("sig1", &mut encoded_bytes);
        write_txn_with_sig("sig2", &mut encoded_bytes);
        write_txn_with_sig("sig3", &mut encoded_bytes);

        let mut source = Cursor::new(encoded_bytes);

        let mut txn_stream: TransactionSource = LengthDelimitedMessageSource::new(&mut source);

        let mut txns = txn_stream.next(2).unwrap();
        assert_eq!(txns.len(), 2);

        // ensure that it is exhausted, even when more are requested
        txns = txn_stream.next(2).unwrap();
        assert_eq!(txns.len(), 1);
    }

    #[test]
    fn signed_batches_empty_transactions() {
        let encoded_bytes: Vec<u8> = Vec::new();
        let mut source = Cursor::new(encoded_bytes);

        let context = MockContext;
        let crypto_factory = signing::CryptoFactory::new(&context);
        let private_key = MockPrivateKey;
        let signer = crypto_factory.new_signer(&private_key);

        let mut producer = SignedBatchProducer::new(&mut source, 2, &signer);
        let batch_result = producer.next();

        assert!(batch_result.is_none());
    }

    #[test]
    fn signed_batches_single_transaction() {
        let mut encoded_bytes: Vec<u8> = Vec::new();
        write_txn_with_sig("sig1", &mut encoded_bytes);

        let mut source = Cursor::new(encoded_bytes);

        let context = MockContext;
        let crypto_factory = signing::CryptoFactory::new(&context);
        let private_key = MockPrivateKey;
        let signer = crypto_factory.new_signer(&private_key);

        let mut producer = SignedBatchProducer::new(&mut source, 2, &signer);
        let mut batch_result = producer.next();
        assert!(batch_result.is_some());

        let batch = batch_result.unwrap().unwrap();

        let batch_header: BatchHeader = protobuf::parse_from_bytes(&batch.header).unwrap();
        assert_eq!(batch_header.transaction_ids.len(), 1);
        assert_eq!(batch_header.transaction_ids[0], String::from("sig1"));

        // test exhaustion
        batch_result = producer.next();
        assert!(batch_result.is_none());
    }

    #[test]
    fn signed_batches_multiple_batches() {
        let mut encoded_bytes: Vec<u8> = Vec::new();

        write_txn_with_sig("sig1", &mut encoded_bytes);
        write_txn_with_sig("sig2", &mut encoded_bytes);
        write_txn_with_sig("sig3", &mut encoded_bytes);

        let mut source = Cursor::new(encoded_bytes);

        let context = MockContext;
        let crypto_factory = signing::CryptoFactory::new(&context);
        let private_key = MockPrivateKey;
        let signer = crypto_factory.new_signer(&private_key);

        let mut producer = SignedBatchProducer::new(&mut source, 2, &signer);
        let mut batch_result = producer.next();
        assert!(batch_result.is_some());

        let batch = batch_result.unwrap().unwrap();

        let batch_header: BatchHeader = protobuf::parse_from_bytes(&batch.header).unwrap();
        assert_eq!(batch_header.transaction_ids.len(), 2);
        assert_eq!(batch_header.transaction_ids[0], String::from("sig1"));
        assert_eq!(batch_header.transaction_ids[1], String::from("sig2"));
        assert_eq!(
            batch.header_signature,
            String::from("signed by mock_algorithm")
        );

        // pull the next batch
        batch_result = producer.next();
        assert!(batch_result.is_some());

        let batch = batch_result.unwrap().unwrap();

        let batch_header: BatchHeader = protobuf::parse_from_bytes(&batch.header).unwrap();
        assert_eq!(batch_header.transaction_ids.len(), 1);
        assert_eq!(batch_header.transaction_ids[0], String::from("sig3"));

        // test exhaustion
        batch_result = producer.next();
        assert!(batch_result.is_none());
    }

    #[test]
    fn generate_signed_batches() {
        let mut encoded_bytes: Vec<u8> = Vec::new();

        write_txn_with_sig("sig1", &mut encoded_bytes);
        write_txn_with_sig("sig2", &mut encoded_bytes);
        write_txn_with_sig("sig3", &mut encoded_bytes);

        let mut source = Cursor::new(encoded_bytes);
        let output_bytes: Vec<u8> = Vec::new();
        let mut output = Cursor::new(output_bytes);

        let context = MockContext;
        let private_key = MockPrivateKey;

        super::generate_signed_batches(&mut source, &mut output, 2, &context, &private_key)
            .expect("Should have generated batches!");

        // reset for reading
        output.set_position(0);
        let mut batch_source: BatchSource = LengthDelimitedMessageSource::new(&mut output);

        let batch = &(batch_source.next(1).unwrap())[0];
        let batch_header: BatchHeader = protobuf::parse_from_bytes(&batch.header).unwrap();
        assert_eq!(batch_header.transaction_ids.len(), 2);
        assert_eq!(batch_header.transaction_ids[0], String::from("sig1"));
        assert_eq!(batch_header.transaction_ids[1], String::from("sig2"));

        let batch = &(batch_source.next(1).unwrap())[0];
        let batch_header: BatchHeader = protobuf::parse_from_bytes(&batch.header).unwrap();
        assert_eq!(batch_header.transaction_ids.len(), 1);
        assert_eq!(batch_header.transaction_ids[0], String::from("sig3"));
    }

    fn make_txn(sig: &str) -> Transaction {
        let mut txn_header = TransactionHeader::new();

        txn_header.set_batcher_public_key(String::from("some_public_key"));
        txn_header.set_family_name(String::from("test_family"));
        txn_header.set_family_version(String::from("1.0"));
        txn_header.set_signer_public_key(String::from("some_public_key"));
        txn_header.set_payload_sha512(String::from("some_sha512_hash"));

        let mut txn = Transaction::new();
        txn.set_header(txn_header.write_to_bytes().unwrap());
        txn.set_header_signature(String::from(sig));
        txn.set_payload(sig.as_bytes().to_vec());

        txn
    }

    fn write_txn_with_sig(sig: &str, out: &mut Write) {
        let txn = make_txn(sig);
        txn.write_length_delimited_to_writer(out)
            .expect("Unable to write delimiter");
    }

    struct MockContext;

    impl signing::Context for MockContext {
        fn get_algorithm_name(&self) -> &str {
            "mock_algorithm"
        }

        fn sign(
            &self,
            _message: &[u8],
            _key: &signing::PrivateKey,
        ) -> Result<String, signing::Error> {
            Ok(String::from("signed by mock_algorithm"))
        }

        fn verify(
            &self,
            _signature: &str,
            _message: &[u8],
            _key: &signing::PublicKey,
        ) -> Result<bool, signing::Error> {
            Ok(true)
        }

        fn get_public_key(
            &self,
            _private_key: &signing::PrivateKey,
        ) -> Result<Box<signing::PublicKey>, signing::Error> {
            Ok(Box::new(MockPublicKey))
        }

        fn new_random_private_key(&self) -> Result<Box<signing::PrivateKey>, signing::Error> {
            Ok(Box::new(MockPrivateKey))
        }
    }

    struct MockPublicKey;

    impl signing::PublicKey for MockPublicKey {
        fn get_algorithm_name(&self) -> &str {
            "mock_algorithm"
        }

        fn as_hex(&self) -> String {
            String::from("123456789abcdef")
        }

        fn as_slice(&self) -> &[u8] {
            "123456789abcdef".as_bytes()
        }
    }

    struct MockPrivateKey;

    impl signing::PrivateKey for MockPrivateKey {
        fn get_algorithm_name(&self) -> &str {
            "mock_algorithm"
        }

        fn as_hex(&self) -> String {
            String::from("123456789abcdef123456789abcdef")
        }

        fn as_slice(&self) -> &[u8] {
            "123456789abcdef123456789abcdef".as_bytes()
        }
    }
}
