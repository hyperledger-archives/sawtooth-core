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

pub mod error;
pub mod identity_view;
pub mod merkle;
pub mod merkle_ffi;
pub mod settings_view;
pub mod state_pruning_manager;

use state::error::StateDatabaseError;

pub trait StateReader {
    /// Returns true if the given address exists in State; false, otherwise.
    ///
    /// Will return a StateDatabaseError if any errors occur while querying for
    /// the existence of the given address.
    fn contains(&self, address: &str) -> Result<bool, StateDatabaseError>;

    /// Returns the data for a given address, if it exists.  In the case where
    /// the address exists, but has no data, it will return None.
    ///
    /// Will return an StateDatabaseError::NotFound, if the given address is not
    /// in State.
    fn get(&self, address: &str) -> Result<Option<Vec<u8>>, StateDatabaseError>;

    /// A state value is considered a leaf if it has data stored at the address.
    ///
    /// Returns an iterator over address-value pairs in state.
    ///
    /// Returns Err if the prefix is invalid, or if any other database errors
    /// occur while creating the iterator.
    fn leaves(
        &self,
        prefix: Option<&str>,
    ) -> Result<
        Box<Iterator<Item = Result<(String, Vec<u8>), StateDatabaseError>>>,
        StateDatabaseError,
    >;
}
