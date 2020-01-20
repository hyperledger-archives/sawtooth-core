// Copyright 2019 Cargill Incorporated
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

mod error;

use std::ops::Bound;

use transact::protocol::receipt::TransactionReceipt;
use transact::protos::{FromBytes as ReceiptFromBytes, IntoBytes};

use crate::store::{AsBytes, FromBytes, OrderedStore, OrderedStoreRange};

pub use self::error::TransactionReceiptStoreError;

impl AsBytes for TransactionReceipt {
    fn as_bytes(&self) -> Vec<u8> {
        self.clone()
            .into_bytes()
            .expect("failed to serialize transaction receipt")
    }
}

impl FromBytes for TransactionReceipt {
    fn from_bytes(bytes: &[u8]) -> Result<Self, String> {
        <TransactionReceipt as ReceiptFromBytes<TransactionReceipt>>::from_bytes(bytes)
            .map_err(|err| err.to_string())
    }
}

/// `TransactionReceiptStore` is a wrapper around an `OrderedStore` that stores
/// `TransactionReceipt`s keyed by transaction IDs (`String`s) and indexed by `u64`s to provide
/// ordering of transactions.
pub struct TransactionReceiptStore(Box<dyn OrderedStore<String, TransactionReceipt, u64>>);

impl TransactionReceiptStore {
    /// Create a new `TransactionReceiptStore` that is backed by the given `OrderedStore`.
    pub fn new(store: Box<dyn OrderedStore<String, TransactionReceipt, u64>>) -> Self {
        Self(store)
    }

    /// Get the `TransactionReceipt` that matches the given transaction ID.
    pub fn get_by_id(
        &self,
        id: String,
    ) -> Result<Option<TransactionReceipt>, TransactionReceiptStoreError> {
        Ok(self.0.get_value_by_key(&id)?)
    }

    /// Get the `TransactionReceipt` at the given index.
    pub fn get_by_index(
        &self,
        idx: u64,
    ) -> Result<Option<TransactionReceipt>, TransactionReceiptStoreError> {
        Ok(self.0.get_value_by_index(&idx)?)
    }

    /// Get the number of `TransactionReceipt`s in the store.
    pub fn count(&self) -> Result<u64, TransactionReceiptStoreError> {
        Ok(self.0.count()?)
    }

    /// Get an iterator over all `TransactionReceipt`s in order.
    pub fn iter<'a>(
        &'a self,
    ) -> Result<
        Box<dyn Iterator<Item = TransactionReceipt> + 'a + Send>,
        TransactionReceiptStoreError,
    > {
        Ok(self.0.iter()?)
    }

    /// Get an iterator over all `TransactionReceipt`s since the one with the given ID.
    pub fn iter_since_id<'a>(
        &'a self,
        id: String,
    ) -> Result<
        Box<dyn Iterator<Item = TransactionReceipt> + 'a + Send>,
        TransactionReceiptStoreError,
    > {
        let idx = self
            .0
            .get_index_by_key(&id)?
            .ok_or_else(|| TransactionReceiptStoreError::IdNotFound)?;
        let range = OrderedStoreRange {
            start: Bound::Excluded(idx),
            end: Bound::Unbounded,
        };
        Ok(self.0.range_iter(range)?)
    }

    /// Add receipts to the end of the store.
    pub fn append(
        &mut self,
        receipts: Vec<TransactionReceipt>,
    ) -> Result<(), TransactionReceiptStoreError> {
        for receipt in receipts {
            self.0
                .insert(receipt.transaction_id.clone(), receipt, self.count()?)?;
        }
        Ok(())
    }

    /// Remove the `TransactionReceipt` with the given ID.
    pub fn remove_by_id(
        &mut self,
        id: String,
    ) -> Result<Option<TransactionReceipt>, TransactionReceiptStoreError> {
        Ok(self.0.remove_by_key(&id)?.map(|(val, _)| val))
    }

    /// Remove the `TransactionReceipt` at the given index.
    pub fn remove_by_index(
        &mut self,
        idx: u64,
    ) -> Result<Option<TransactionReceipt>, TransactionReceiptStoreError> {
        Ok(self.0.remove_by_index(&idx)?.map(|(_, val)| val))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    use transact::protocol::receipt::TransactionReceiptBuilder;

    /// Test that a receipt store works properly.
    fn test_receipt_store(mut receipt_store: TransactionReceiptStore) {
        assert_eq!(receipt_store.count().expect("Failed to get count"), 0);

        let receipt1 = TransactionReceiptBuilder::new()
            .valid()
            .with_transaction_id("ab".into())
            .build()
            .expect("failed to build receipt1");
        let receipt2 = TransactionReceiptBuilder::new()
            .invalid()
            .with_transaction_id("cd".into())
            .build()
            .expect("failed to build receipt2");

        receipt_store
            .append(vec![receipt1.clone(), receipt2.clone()])
            .expect("Failed to append");
        assert_eq!(receipt_store.count().expect("Failed to get count"), 2);

        assert_eq!(
            receipt_store
                .get_by_index(0)
                .expect("Failed to get by index"),
            Some(receipt1.clone())
        );
        assert_eq!(
            receipt_store
                .get_by_index(2)
                .expect("Failed to get by index"),
            None
        );

        assert_eq!(
            receipt_store
                .get_by_id(receipt1.transaction_id.clone())
                .expect("Failed to get by id"),
            Some(receipt1.clone())
        );
        assert_eq!(
            receipt_store
                .get_by_id("01".into())
                .expect("Failed to get by id"),
            None
        );

        assert_eq!(
            receipt_store
                .iter()
                .expect("Failed to get iter")
                .collect::<Vec<_>>(),
            vec![receipt1.clone(), receipt2.clone()]
        );

        assert_eq!(
            receipt_store
                .iter_since_id(receipt1.transaction_id.clone())
                .expect("Failed to get iter of receipts after 1")
                .collect::<Vec<_>>(),
            vec![receipt2.clone()]
        );

        assert_eq!(
            receipt_store
                .remove_by_index(2)
                .expect("Failed to remove by index"),
            None
        );
        assert_eq!(receipt_store.count().expect("Failed to get count"), 2);
        assert_eq!(
            receipt_store
                .remove_by_index(1)
                .expect("Failed to remove by index"),
            Some(receipt2.clone()),
        );
        assert_eq!(
            receipt_store
                .get_by_index(1)
                .expect("Failed to get by index"),
            None
        );
        assert_eq!(
            receipt_store
                .get_by_id(receipt2.transaction_id.clone())
                .expect("Failed to get by id"),
            None
        );
        assert_eq!(receipt_store.count().expect("Failed to get count"), 1);

        assert_eq!(
            receipt_store
                .remove_by_id("ef".into())
                .expect("Failed to remove by id"),
            None
        );
        assert_eq!(receipt_store.count().expect("Failed to get count"), 1);
        assert_eq!(
            receipt_store
                .remove_by_id(receipt1.transaction_id.clone())
                .expect("Failed to remove by id"),
            Some(receipt1.clone()),
        );
        assert_eq!(
            receipt_store
                .get_by_index(0)
                .expect("Failed to get by index"),
            None
        );
        assert_eq!(
            receipt_store
                .get_by_id(receipt1.transaction_id.clone())
                .expect("Failed to get by id"),
            None
        );
        assert_eq!(receipt_store.count().expect("Failed to get count"), 0);
    }

    /// Test that a BTree-backed receipt store works properly.
    #[cfg(feature = "btree-store")]
    #[test]
    fn btree_receipt_store() {
        test_receipt_store(TransactionReceiptStore::new(Box::new(
            crate::store::btree::BTreeOrderedStore::new(),
        )))
    }

    /// Test that an LMDB-backed receipt store works properly.
    #[cfg(feature = "lmdb-store")]
    #[test]
    fn lmdb_receipt_store() {
        let mut temp_db_path = std::env::temp_dir();
        let thread_id = std::thread::current().id();
        temp_db_path.push(format!("store-{:?}.lmdb", thread_id));

        let test_result = std::panic::catch_unwind(|| {
            test_receipt_store(TransactionReceiptStore::new(Box::new(
                crate::store::lmdb::LmdbOrderedStore::new(
                    temp_db_path.as_path(),
                    Some(1024 * 1024),
                )
                .expect("Failed to create LMDB ordered store"),
            )))
        });

        std::fs::remove_file(temp_db_path.as_path()).expect("Failed to remove temp DB file");

        assert!(test_result.is_ok());
    }
}
