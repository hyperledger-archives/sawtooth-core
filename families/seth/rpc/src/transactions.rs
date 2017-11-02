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

use protobuf;

use messages::seth::{
    SethTransaction_TransactionType,
    SethTransaction as SethTrasactionPb,
    SethTransactionReceipt,
    CreateExternalAccountTxn as CreateExternalAccountTxnPb,
    CreateContractAccountTxn as CreateContractAccountTxnPb,
    MessageCallTxn as MessageCallTxnPb,
    SetPermissionsTxn as SetPermissionsTxnPb,
};

use sawtooth_sdk::messages::transaction::{
    Transaction as TransactionPb,
    TransactionHeader,
};
use sawtooth_sdk::messages::transaction_receipt::{TransactionReceipt};
use sawtooth_sdk::messages::events::{Event, Event_Attribute};

use client::{
    Error,
    BlockKey,
};
use transform;
use accounts::public_key_to_address;

pub enum SethTransaction {
    CreateExternalAccount(CreateExternalAccountTxnPb),
    CreateContractAccount(CreateContractAccountTxnPb),
    MessageCall(MessageCallTxnPb),
    SetPermissions(SetPermissionsTxnPb),
}

impl SethTransaction {
    pub fn try_from(mut txn: SethTrasactionPb) -> Option<Self> {
        match txn.transaction_type {
            SethTransaction_TransactionType::CREATE_EXTERNAL_ACCOUNT =>
                Some(SethTransaction::CreateExternalAccount(txn.take_create_external_account())),
            SethTransaction_TransactionType::CREATE_CONTRACT_ACCOUNT =>
                Some(SethTransaction::CreateContractAccount(txn.take_create_contract_account())),
            SethTransaction_TransactionType::MESSAGE_CALL =>
                Some(SethTransaction::MessageCall(txn.take_message_call())),
            SethTransaction_TransactionType::SET_PERMISSIONS =>
                Some(SethTransaction::SetPermissions(txn.take_set_permissions())),
            _ => None,
        }
    }

    pub fn to_pb(&self) -> SethTrasactionPb {
        let mut txn = SethTrasactionPb::new();
        match self {
            &SethTransaction::CreateExternalAccount(ref inner) => {
                txn.set_transaction_type(SethTransaction_TransactionType::CREATE_EXTERNAL_ACCOUNT);
                txn.set_create_external_account(inner.clone());
            },
            &SethTransaction::CreateContractAccount(ref inner) => {
                txn.set_transaction_type(SethTransaction_TransactionType::CREATE_CONTRACT_ACCOUNT);
                txn.set_create_contract_account(inner.clone());
            },
            &SethTransaction::MessageCall(ref inner) => {
                txn.set_transaction_type(SethTransaction_TransactionType::MESSAGE_CALL);
                txn.set_message_call(inner.clone());
            },
            &SethTransaction::SetPermissions(ref inner) => {
                txn.set_transaction_type(SethTransaction_TransactionType::SET_PERMISSIONS);
                txn.set_set_permissions(inner.clone());
            },
        }
        txn
    }
}

pub enum TransactionKey {
    Signature(String),
    Index((u64, BlockKey)),
}

pub struct Transaction {
    signer_public_key: String,
    signature: String,
    inner: SethTransaction,
}

impl Transaction {
    pub fn try_from(mut txn: TransactionPb) -> Result<Self, Error> {
        let mut header: TransactionHeader =
            protobuf::parse_from_bytes(&txn.header)
                .map_err(|_| Error::ParseError(String::from("Failed to parse header")))?;
        let inner: Option<SethTransaction> =
            protobuf::parse_from_bytes(&txn.payload)
                .map_err(|_| Error::ParseError(String::from("Failed to parse payload")))
                .map(|seth_txn_pb| SethTransaction::try_from(seth_txn_pb))?;
        match inner {
            Some(seth_txn) => Ok(Transaction{
                signer_public_key: header.take_signer_public_key(),
                signature: txn.take_header_signature(),
                inner: seth_txn,
            }),
            None => Err(Error::ParseError(String::from("Not a valid seth transaction"))),
        }
    }

    // Helper methods that are the same for all transaction types
    pub fn hash(&self) -> String {
        self.signature.clone()
    }

    pub fn nonce(&self) -> u64 {
        match self.inner {
            SethTransaction::CreateExternalAccount(ref txn) => txn.nonce,
            SethTransaction::CreateContractAccount(ref txn) => txn.nonce,
            SethTransaction::MessageCall(ref txn) => txn.nonce,
            SethTransaction::SetPermissions(ref txn) => txn.nonce,
        }
    }

    pub fn gas_limit(&self) -> Option<u64> {
        match self.inner {
            SethTransaction::CreateExternalAccount(_) => None,
            SethTransaction::CreateContractAccount(ref txn) => Some(txn.gas_limit),
            SethTransaction::MessageCall(ref txn) => Some(txn.gas_limit),
            SethTransaction::SetPermissions(_) => None,
        }
    }

    pub fn from_addr(&self) -> String {
        public_key_to_address(&transform::hex_str_to_bytes(&self.signer_public_key).unwrap())
    }

    pub fn to_addr(&self) -> Option<String> {
        match self.inner {
            SethTransaction::CreateExternalAccount(ref txn) => Some(transform::bytes_to_hex_str(&txn.to)),
            SethTransaction::CreateContractAccount(_) => None,
            SethTransaction::MessageCall(ref txn) => Some(transform::bytes_to_hex_str(&txn.to)),
            SethTransaction::SetPermissions(ref txn) => Some(transform::bytes_to_hex_str(&txn.to)),
        }
    }

    pub fn data(&self) -> Option<String> {
        match self.inner {
            SethTransaction::CreateExternalAccount(_) => None,
            SethTransaction::CreateContractAccount(_) => None,
            SethTransaction::MessageCall(ref txn) => Some(transform::bytes_to_hex_str(&txn.data)),
            SethTransaction::SetPermissions(_) => None,
        }
    }
}

#[derive(Debug,Clone)]
pub struct SethLog {
    pub address: String,
    pub topics: Vec<String>,
    pub data: String,
}

impl SethLog {
    pub fn from_event_pb(event: &Event) -> Result<SethLog, Error>{
        let address: String = event.get_attributes().iter()
            .find(|attr| attr.key == "address")
            .map(|attr| String::from(attr.get_value()))
            .ok_or_else(|| Error::ParseError(String::from("Missing `address` attribute")))?;

        let mut topic_attrs: Vec<&Event_Attribute> = event.get_attributes().iter()
            .filter(|attr| attr.key.get(..5) == Some("topic"))
            .collect::<Vec<&Event_Attribute>>();
        topic_attrs.sort_by(|a, b| a.key.cmp(&b.key));
        let topics: Vec<String> = topic_attrs.iter()
            .map(|attr| String::from(attr.value.as_str()))
            .collect();

        let data: String = transform::bytes_to_hex_str(event.get_data());

        Ok(SethLog {
            address: address,
            topics: topics,
            data: data,
        })
    }
}

pub struct SethReceipt {
    pub transaction_id: String,
    pub contract_address: String,
    pub gas_used: u64,
    pub return_value: String,
    pub logs: Vec<SethLog>,
}

impl SethReceipt {
    pub fn from_receipt_pb(receipt: &TransactionReceipt) -> Result<SethReceipt, Error>{
        let seth_receipt_pbs: Vec<SethTransactionReceipt> = receipt.get_data().iter()
             .map(|d: &Vec<u8>| {
                let r: Result<SethTransactionReceipt, Error> =
                    protobuf::parse_from_bytes(d.as_slice())
                        .map_err(|error|
                            Error::ParseError(format!(
                                "Failed to deserialize Seth receipt: {:?}", error)));
                r
            }).collect::<Result<Vec<SethTransactionReceipt>, Error>>()?;

        let seth_receipt_pb = seth_receipt_pbs.get(0).ok_or_else(||
            Error::ParseError(String::from("Receipt doesn't contain any seth receipts")))?;

        let logs = receipt.get_events().iter()
            .filter(|e| e.event_type == "seth_log_event")
            .map(SethLog::from_event_pb)
            .collect::<Result<Vec<SethLog>, Error>>()?;

        let contract_address = transform::bytes_to_hex_str(seth_receipt_pb.get_contract_address());
        let gas_used = seth_receipt_pb.get_gas_used();
        let return_value = transform::bytes_to_hex_str(seth_receipt_pb.get_return_value());

        Ok(SethReceipt {
            transaction_id: String::from(receipt.get_transaction_id()),
            contract_address: contract_address,
            gas_used: gas_used,
            return_value: return_value,
            logs: logs,
        })
    }
}
