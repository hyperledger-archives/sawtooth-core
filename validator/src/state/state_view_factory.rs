/*
 * Copyright 2018 Bitwise IO
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
use database::lmdb::LmdbDatabase;
use state::error::StateDatabaseError;
use state::merkle::{DecodedMerkleStateReader, MerkleDatabase};
use state::StateReader;

/// The StateViewFactory produces StateViews for a particular merkle root.
///
/// This factory produces read-only views of a merkle tree. For a given
/// database, these views are considered immutable.
#[derive(Clone)]
pub struct StateViewFactory {
    state_database: LmdbDatabase,
}

impl StateViewFactory {
    pub fn new(state_database: LmdbDatabase) -> Self {
        StateViewFactory { state_database }
    }

    /// Creates a state view for a given state root hash.
    pub fn create_view<V: From<Box<StateReader>>>(
        &self,
        state_root_hash: &str,
    ) -> Result<V, StateDatabaseError> {
        let merkle_db = DecodedMerkleStateReader::new(MerkleDatabase::new(
            self.state_database.clone(),
            Some(state_root_hash),
        )?);
        Ok(V::from(Box::new(merkle_db)))
    }
}
