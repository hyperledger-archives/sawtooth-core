use std::time::Instant;

use crypto::digest::Digest;
use crypto::sha2::Sha512;

use protobuf;
use protobuf::Message;

use sawtooth_sdk::messages::batch::{ Batch, BatchHeader, BatchList };
use sawtooth_sdk::messages::transaction::{ Transaction, TransactionHeader };
use sawtooth_sdk::signing::Signer;

use serde_cbor::{ to_vec };

use errors::IntkeyError;
use maketx::{ IntkeyPayload };



const INTKEY_FAMILY_NAME: &'static str = "intkey";
const INTKEY_FAMILY_VERSION: &'static str = "1.0";

fn create_nonce() -> String {
    let elapsed = Instant::now().elapsed();
    format!("{}{}", elapsed.as_secs(), elapsed.subsec_nanos())
}

pub fn create_transaction(
    _payload: IntkeyPayload,
    _signer: &Signer,
    _public_key: &String,
) -> Result<Transaction, IntkeyError> {
    let mut txn = Transaction::new();
    let mut txn_header = TransactionHeader::new();

        txn_header.set_family_name(String::from(INTKEY_FAMILY_NAME));
        txn_header.set_family_version(String::from(INTKEY_FAMILY_VERSION));
        txn_header.set_nonce(create_nonce());
        txn_header.set_signer_public_key(_public_key.clone());
        txn_header.set_batcher_public_key(_public_key.clone());

        let cbor_payload = to_vec(&_payload).unwrap();

        let storage_addr = _payload.get_storage_addr();

        let addrs = vec![storage_addr];
        let input_addrs = addrs.clone();
        let output_addrs = addrs.clone();

        let input_pbuf = protobuf::RepeatedField::from_vec(input_addrs);
        let output_pbuf = protobuf::RepeatedField::from_vec(output_addrs);

        txn_header.set_inputs(input_pbuf);
        txn_header.set_outputs(output_pbuf);

        let mut sha = Sha512::new();
        sha.input(&cbor_payload);

        txn_header.set_payload_sha512(sha.result_str());
        txn.set_payload(cbor_payload);

        let txn_header_bytes = txn_header.write_to_bytes()?;
        txn.set_header(txn_header_bytes.clone());

        let b: &[u8] = &txn_header_bytes;
        txn.set_header_signature(_signer.sign(b)?);

        Ok(txn)
        }

pub fn create_batch(
    txn: Transaction,
    signer: &Signer,
    public_key: &String
) -> Result<Batch, IntkeyError> {
    let mut batch = Batch::new();
    let mut batch_header = BatchHeader::new();

    batch_header.set_transaction_ids(protobuf::RepeatedField::from_vec(vec![
        txn.header_signature.clone(),
    ]));
    batch_header.set_signer_public_key(public_key.clone());
    batch.set_transactions(protobuf::RepeatedField::from_vec(vec![txn]));

    let batch_header_bytes = batch_header.write_to_bytes()?;
    batch.set_header(batch_header_bytes.clone());

    let b: &[u8] = &batch_header_bytes;
    batch.set_header_signature(signer.sign(b)?);

Ok(batch)
}

pub fn create_batch_list_from_one(batch: Batch) -> BatchList {
    let mut batch_list = BatchList::new();
    batch_list.set_batches(protobuf::RepeatedField::from_vec(vec![batch]));
    return batch_list;
}