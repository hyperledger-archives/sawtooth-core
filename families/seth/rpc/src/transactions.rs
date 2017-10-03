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
    CreateExternalAccountTxn as CreateExternalAccountTxnPb,
    CreateContractAccountTxn as CreateContractAccountTxnPb,
    MessageCallTxn as MessageCallTxnPb,
    SetPermissionsTxn as SetPermissionsTxnPb,
};

use sawtooth_sdk::messages::transaction::{
    Transaction as TransactionPb,
    TransactionHeader,
};

use client::{
    Error,
    BlockKey,
    bytes_to_hex_str,
    hex_str_to_bytes,
};
use accounts::pubkey_to_address;

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
}

pub enum TransactionKey {
    Signature(String),
    Index((u64, BlockKey)),
}

pub struct Transaction {
    signer_pubkey: String,
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
                signer_pubkey: header.take_signer_pubkey(),
                signature: txn.take_header_signature(),
                inner: seth_txn,
            }),
            None => Err(Error::ParseError(String::from("Not a seth transaction"))),
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

    pub fn inner(&self) -> &SethTransaction {
        &self.inner
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
        pubkey_to_address(&hex_str_to_bytes(&self.signer_pubkey).unwrap())
    }

    pub fn to_addr(&self) -> Option<String> {
        match self.inner {
            SethTransaction::CreateExternalAccount(ref txn) => Some(bytes_to_hex_str(&txn.to)),
            SethTransaction::CreateContractAccount(_) => None,
            SethTransaction::MessageCall(ref txn) => Some(bytes_to_hex_str(&txn.to)),
            SethTransaction::SetPermissions(ref txn) => Some(bytes_to_hex_str(&txn.to)),
        }
    }

    pub fn data(&self) -> Option<String> {
        match self.inner {
            SethTransaction::CreateExternalAccount(_) => None,
            SethTransaction::CreateContractAccount(_) => None,
            SethTransaction::MessageCall(ref txn) => Some(bytes_to_hex_str(&txn.data)),
            SethTransaction::SetPermissions(_) => None,
        }
    }
}
