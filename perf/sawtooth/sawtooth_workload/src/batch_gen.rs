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

extern crate protobuf;

use std::error;
use std::fmt;
use std::io::Read;
use std::io::Write;

use sawtooth_sdk::messages::transaction::Transaction;
use sawtooth_sdk::messages::batch::Batch;
use sawtooth_sdk::messages::batch::BatchHeader;
use self::protobuf::Message;

pub fn generate_signed_batches<'a>(reader: &'a mut Read, writer: &'a mut Write, max_batch_size: usize)
    -> Result<(), BatchingError>
{
    let mut producer = SignedBatchProducer::new(reader, max_batch_size);
    loop {
        match producer.next() {
            Ok(Some(batch)) => {
                if let Err(err) = batch.write_length_delimited_to_writer(writer) {
                    return Err(BatchingError::MessageError(err));
                }
            },
            Ok(None) => break,
            Err(err) => return Err(err),
        }
    }

    Ok(())
}

struct TransactionSource<'a> {
    source: protobuf::CodedInputStream<'a>,
}

impl<'a> TransactionSource<'a> {
    pub fn new(source: &'a mut Read) -> Self {
        let source = protobuf::CodedInputStream::new(source);
        TransactionSource {
            source,
        }
    }

    pub fn next(&mut self, max_txns: usize)
        -> Result<Vec<Transaction>, protobuf::ProtobufError>
    {
        let mut results = Vec::with_capacity(max_txns);
        for _ in 0..max_txns {
            if self.source.eof()? {
                break;
            }

            // read the delimited length
            let next_len = self.source.read_raw_varint32()?;
            let buf =  self.source.read_raw_bytes(next_len)?;
            
            let txn = try!(protobuf::parse_from_bytes(&buf));
            results.push(txn);
        }
        Ok(results)
    }
}

#[derive(Debug)]
pub enum BatchingError {
    MessageError(protobuf::ProtobufError),
    SigningError,
}

impl fmt::Display for BatchingError {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match *self {
            BatchingError::MessageError(ref err) =>
                write!(f, "Error occurred reading messages: {}", err),
            BatchingError::SigningError => write!(f, "Unable to sign batch"),
        }
    }
}

impl error::Error for BatchingError {
    fn description(&self) -> &str {
        match *self {
            BatchingError::MessageError(ref err) => err.description(),
            BatchingError::SigningError => "Unable to sign batch",
        }
    }

    fn cause(&self) -> Option<&error::Error> {
        match *self {
            BatchingError::MessageError(ref err) => Some(err),
            BatchingError::SigningError => None,
        }
    }
}

pub struct SignedBatchProducer<'a> {
    transaction_source: TransactionSource<'a>,
    max_batch_size: usize,
}

pub type BatchResult = Result<Option<Batch>, BatchingError>;

impl<'a> SignedBatchProducer<'a> {
    pub fn new(source: &'a mut Read, max_batch_size: usize) -> Self {
        let transaction_source = TransactionSource::new(source);
        SignedBatchProducer {
            transaction_source,
            max_batch_size,
        }
    }

    pub fn next(&mut self) -> BatchResult {
        let txns = match self.transaction_source.next(self.max_batch_size) {
            Ok(txns) => txns,
            Err(err) => return Err(BatchingError::MessageError(err)),
        };

        if txns.len() == 0 {
            return Ok(None);
        }

        let mut batch_header = BatchHeader::new();

        // set signer_pubkey
        let txn_ids = txns.iter().cloned().map(|mut txn| txn.take_header_signature()).collect();
        batch_header.set_transaction_ids(protobuf::RepeatedField::from_vec(txn_ids));

        let mut batch = Batch::new();
        batch.set_header(batch_header.write_to_bytes().unwrap());
        batch.set_transactions(protobuf::RepeatedField::from_vec(txns));
            
        Ok(Some(batch))
    }
}


#[cfg(test)]
mod tests {
    use super::TransactionSource;
    use super::SignedBatchProducer;
    use std::io::{Cursor, Write};
    use sawtooth_sdk::messages::transaction::{Transaction, TransactionHeader};
    use sawtooth_sdk::messages::batch::BatchHeader;
    use super::protobuf;
    use super::protobuf::Message;

    #[test]
    fn empty_transaction_source() {
        let encoded_bytes: Vec<u8> = Vec::new();
        let mut source = Cursor::new(encoded_bytes);

        let mut txn_stream = TransactionSource::new(&mut source);
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

        let mut txn_stream = TransactionSource::new(&mut source);

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

        let mut producer = SignedBatchProducer::new(&mut source, 2);
        let batch_result = producer.next().unwrap();
        
        assert_eq!(batch_result, None);
    }

    #[test]
    fn signed_batches_single_transaction() {
        let mut encoded_bytes: Vec<u8> = Vec::new();
        write_txn_with_sig("sig1", &mut encoded_bytes);

        let mut source = Cursor::new(encoded_bytes);

        let mut producer = SignedBatchProducer::new(&mut source, 2);
        let mut batch_result = producer.next().unwrap();
        assert!(batch_result.is_some());

        let batch = batch_result.unwrap();

        let batch_header: BatchHeader = protobuf::parse_from_bytes(&batch.header).unwrap();
        assert_eq!(batch_header.transaction_ids.len(), 1);
        assert_eq!(batch_header.transaction_ids[0], String::from("sig1"));

        // test exhaustion
        batch_result = producer.next().unwrap();
        assert_eq!(batch_result, None);
    }

    #[test]
    fn signed_batches_multiple_batches() {
        let mut encoded_bytes: Vec<u8> = Vec::new();

        write_txn_with_sig("sig1", &mut encoded_bytes);
        write_txn_with_sig("sig2", &mut encoded_bytes);
        write_txn_with_sig("sig3", &mut encoded_bytes);

        let mut source = Cursor::new(encoded_bytes);

        let mut producer = SignedBatchProducer::new(&mut source, 2);
        let mut batch_result = producer.next().unwrap();
        assert!(batch_result.is_some());

        let batch = batch_result.unwrap();

        let batch_header: BatchHeader = protobuf::parse_from_bytes(&batch.header).unwrap();
        assert_eq!(batch_header.transaction_ids.len(), 2);
        assert_eq!(batch_header.transaction_ids[0], String::from("sig1"));
        assert_eq!(batch_header.transaction_ids[1], String::from("sig2"));

        // pull the next batch
        batch_result = producer.next().unwrap();
        assert!(batch_result.is_some());

        let batch = batch_result.unwrap();

        let batch_header: BatchHeader = protobuf::parse_from_bytes(&batch.header).unwrap();
        assert_eq!(batch_header.transaction_ids.len(), 1);
        assert_eq!(batch_header.transaction_ids[0], String::from("sig3"));

        // test exhaustion
        batch_result = producer.next().unwrap();
        assert_eq!(batch_result, None);
    }

    fn make_txn(sig: &str) -> Transaction {
        let mut txn_header = TransactionHeader::new();

        txn_header.set_batcher_pubkey(String::from("some_pubkey"));
        txn_header.set_family_name(String::from("test_family"));
        txn_header.set_family_version(String::from("1.0"));
        txn_header.set_signer_pubkey(String::from("some_pubkey"));
        txn_header.set_payload_encoding(String::from("text/string"));
        txn_header.set_payload_sha512(String::from("some_sha512_hash"));

        let mut txn = Transaction::new();
        txn.set_header(txn_header.write_to_bytes().unwrap());
        txn.set_header_signature(String::from(sig));
        txn.set_payload(sig.as_bytes().to_vec());

        txn
    }

    fn write_txn_with_sig(sig: &str, out: &mut Write) {
        let txn = make_txn(sig);
        txn.write_length_delimited_to_writer(out).expect("Unable to write delimiter");
    }
}
