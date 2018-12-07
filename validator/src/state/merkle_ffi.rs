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
use database::lmdb::LmdbDatabase;
use state::error::StateDatabaseError;
use state::merkle::*;
/// This module contains all of the extern C functions for the Merkle trie
use state::StateReader;
use std::collections::HashMap;
use std::ffi::CStr;
use std::mem;
use std::os::raw::{c_char, c_void};
use std::slice;

#[repr(u32)]
#[derive(Debug)]
pub enum ErrorCode {
    Success = 0,
    // Input errors
    NullPointerProvided = 1,
    InvalidHashString = 2,
    InvalidAddress = 3,

    // output errors
    DatabaseError = 0x11,
    NotFound = 0x12,
    InvalidChangeLogIndex = 0x13,

    StopIteration = 0xF0,

    Unknown = 0xFF,
}

#[repr(C)]
#[derive(Debug)]
pub struct Entry {
    address: *const c_char,
    data: *mut u8,
    data_len: usize,
}

#[no_mangle]
pub unsafe extern "C" fn merkle_db_new(
    database: *const c_void,
    merkle_db: *mut *const c_void,
) -> ErrorCode {
    make_merkle_db(database, None, merkle_db)
}

#[no_mangle]
pub unsafe extern "C" fn merkle_db_new_with_root(
    database: *const c_void,
    root: *const c_char,
    merkle_db: *mut *const c_void,
) -> ErrorCode {
    if root.is_null() {
        return ErrorCode::NullPointerProvided;
    }

    let state_root = match CStr::from_ptr(root).to_str() {
        Ok(s) => Some(s),
        Err(_) => return ErrorCode::InvalidHashString,
    };

    make_merkle_db(database, state_root, merkle_db)
}

unsafe fn make_merkle_db(
    database: *const c_void,
    root: Option<&str>,
    merkle_db: *mut *const c_void,
) -> ErrorCode {
    if database.is_null() {
        return ErrorCode::NullPointerProvided;
    }

    let db_ref = (database as *const LmdbDatabase).as_ref().unwrap();
    match MerkleDatabase::new(db_ref.clone(), root) {
        Ok(new_merkle_tree) => {
            *merkle_db = Box::into_raw(Box::new(new_merkle_tree)) as *const c_void;
            ErrorCode::Success
        }
        Err(StateDatabaseError::DatabaseError(err)) => {
            error!("A Database Error occurred: {}", err);
            ErrorCode::DatabaseError
        }
        Err(StateDatabaseError::NotFound(_)) => ErrorCode::NotFound,
        Err(err) => {
            error!("Unknown Error!: {:?}", err);
            ErrorCode::Unknown
        }
    }
}

#[no_mangle]
pub unsafe extern "C" fn merkle_db_drop(merkle_db: *mut c_void) -> ErrorCode {
    if merkle_db.is_null() {
        return ErrorCode::NullPointerProvided;
    }

    Box::from_raw(merkle_db as *mut MerkleDatabase);
    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn merkle_db_get_merkle_root(
    merkle_db: *mut c_void,
    merkle_root: *mut *const u8,
    merkle_root_len: *mut usize,
    merkle_root_cap: *mut usize,
) -> ErrorCode {
    if merkle_db.is_null() {
        return ErrorCode::NullPointerProvided;
    }

    let state_root = (*(merkle_db as *mut MerkleDatabase)).get_merkle_root();
    *merkle_root_cap = state_root.capacity();
    *merkle_root_len = state_root.len();
    *merkle_root = state_root.as_str().as_ptr();

    mem::forget(state_root);

    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn merkle_db_set_merkle_root(
    merkle_db: *mut c_void,
    root: *const c_char,
) -> ErrorCode {
    if merkle_db.is_null() {
        return ErrorCode::NullPointerProvided;
    }
    if root.is_null() {
        return ErrorCode::NullPointerProvided;
    }

    let state_root = match CStr::from_ptr(root).to_str() {
        Ok(s) => s,
        Err(_) => return ErrorCode::InvalidHashString,
    };

    match (*(merkle_db as *mut MerkleDatabase)).set_merkle_root(state_root) {
        Ok(()) => ErrorCode::Success,
        Err(StateDatabaseError::DatabaseError(err)) => {
            error!("A Database Error occurred: {}", err);
            ErrorCode::DatabaseError
        }
        Err(StateDatabaseError::NotFound(_)) => ErrorCode::NotFound,
        Err(err) => {
            error!("Unknown Error!: {:?}", err);
            ErrorCode::Unknown
        }
    }
}

#[no_mangle]
/// Returns ErrorCode.Success if the address is contained, error otherwise.
/// Most likely, this error is ErrorCode.NotFound
pub unsafe extern "C" fn merkle_db_contains(
    merkle_db: *mut c_void,
    address: *const c_char,
) -> ErrorCode {
    if merkle_db.is_null() {
        return ErrorCode::NullPointerProvided;
    }
    if address.is_null() {
        return ErrorCode::NullPointerProvided;
    }

    let address_str = match CStr::from_ptr(address).to_str() {
        Ok(s) => s,
        Err(_) => return ErrorCode::InvalidAddress,
    };

    match (*(merkle_db as *mut MerkleDatabase)).contains(address_str) {
        Ok(true) => ErrorCode::Success,
        Ok(false) => ErrorCode::NotFound,
        Err(StateDatabaseError::DatabaseError(err)) => {
            error!("A Database Error occurred: {}", err);
            ErrorCode::DatabaseError
        }
        Err(StateDatabaseError::NotFound(_)) => ErrorCode::NotFound,
        Err(err) => {
            error!("Unknown Error!: {:?}", err);
            ErrorCode::Unknown
        }
    }
}

#[no_mangle]
pub unsafe extern "C" fn merkle_db_get(
    merkle_db: *mut c_void,
    address: *const c_char,
    bytes: *mut *const u8,
    bytes_len: *mut usize,
    bytes_cap: *mut usize,
) -> ErrorCode {
    if merkle_db.is_null() {
        return ErrorCode::NullPointerProvided;
    }
    if address.is_null() {
        return ErrorCode::NullPointerProvided;
    }

    let address_str = match CStr::from_ptr(address).to_str() {
        Ok(s) => s,
        Err(_) => return ErrorCode::InvalidAddress,
    };

    match (*(merkle_db as *mut MerkleDatabase)).get(address_str) {
        Ok(Some(data_vec)) => {
            *bytes_cap = data_vec.capacity();
            *bytes_len = data_vec.len();
            *bytes = data_vec.as_slice().as_ptr();

            // It will be up to the callee to cleanup this memory
            mem::forget(data_vec);

            ErrorCode::Success
        }
        Ok(None) => ErrorCode::NotFound,
        Err(StateDatabaseError::DatabaseError(err)) => {
            error!("A Database Error occurred: {}", err);
            ErrorCode::DatabaseError
        }
        Err(StateDatabaseError::NotFound(_)) => ErrorCode::NotFound,
        Err(err) => {
            error!("Unknown Error!: {:?}", err);
            ErrorCode::Unknown
        }
    }
}

#[no_mangle]
pub unsafe extern "C" fn merkle_db_set(
    merkle_db: *mut c_void,
    address: *const c_char,
    data: *const u8,
    data_len: usize,
    merkle_root: *mut *const u8,
    merkle_root_len: *mut usize,
    merkle_root_cap: *mut usize,
) -> ErrorCode {
    if merkle_db.is_null() {
        return ErrorCode::NullPointerProvided;
    }
    if address.is_null() {
        return ErrorCode::NullPointerProvided;
    }

    if data.is_null() {
        return ErrorCode::NullPointerProvided;
    }

    let address_str = match CStr::from_ptr(address).to_str() {
        Ok(s) => s,
        Err(_) => return ErrorCode::InvalidHashString,
    };

    let data = slice::from_raw_parts(data, data_len);

    match (*(merkle_db as *mut MerkleDatabase)).set(address_str, data) {
        Ok(state_root) => {
            *merkle_root_cap = state_root.capacity();
            *merkle_root_len = state_root.len();
            *merkle_root = state_root.as_str().as_ptr();

            mem::forget(state_root);

            ErrorCode::Success
        }
        Err(StateDatabaseError::DatabaseError(err)) => {
            error!("A Database Error occurred: {}", err);
            ErrorCode::DatabaseError
        }
        Err(err) => {
            error!("Unknown Error!: {:?}", err);
            ErrorCode::Unknown
        }
    }
}

#[no_mangle]
pub unsafe extern "C" fn merkle_db_delete(
    merkle_db: *mut c_void,
    address: *const c_char,
    merkle_root: *mut *const u8,
    merkle_root_len: *mut usize,
    merkle_root_cap: *mut usize,
) -> ErrorCode {
    if merkle_db.is_null() {
        return ErrorCode::NullPointerProvided;
    }
    if address.is_null() {
        return ErrorCode::NullPointerProvided;
    }

    let address_str = match CStr::from_ptr(address).to_str() {
        Ok(s) => s,
        Err(_) => return ErrorCode::InvalidHashString,
    };

    match (*(merkle_db as *mut MerkleDatabase)).delete(address_str) {
        Ok(state_root) => {
            *merkle_root_cap = state_root.capacity();
            *merkle_root_len = state_root.len();
            *merkle_root = state_root.as_str().as_ptr();

            mem::forget(state_root);

            ErrorCode::Success
        }
        Err(StateDatabaseError::DatabaseError(err)) => {
            error!("A Database Error occurred: {}", err);
            ErrorCode::DatabaseError
        }
        Err(StateDatabaseError::NotFound(_)) => ErrorCode::NotFound,
        Err(err) => {
            error!("Unknown Error!: {:?}", err);
            ErrorCode::Unknown
        }
    }
}

#[no_mangle]
pub unsafe extern "C" fn merkle_db_update(
    merkle_db: *mut c_void,
    updates: *const *const c_void,
    updates_len: usize,
    deletes: *const *const c_char,
    deletes_len: usize,
    virtual_write: bool,
    merkle_root: *mut *const u8,
    merkle_root_len: *mut usize,
    merkle_root_cap: *mut usize,
) -> ErrorCode {
    if merkle_db.is_null() {
        return ErrorCode::NullPointerProvided;
    }

    if updates_len > 0 && updates.is_null() {
        return ErrorCode::NullPointerProvided;
    }

    if deletes_len > 0 && deletes.is_null() {
        return ErrorCode::NullPointerProvided;
    }

    let update_map: HashMap<String, Vec<u8>> = {
        let update_vec: Result<Vec<(String, Vec<u8>)>, ErrorCode> = if updates_len > 0 {
            slice::from_raw_parts(updates, updates_len)
                .iter()
                .map(|ptr| {
                    let entry = *ptr as *const Entry;
                    let address = match CStr::from_ptr((*entry).address).to_str() {
                        Ok(s) => String::from(s),
                        Err(_) => return Err(ErrorCode::InvalidAddress),
                    };
                    let data = slice::from_raw_parts((*entry).data, (*entry).data_len);

                    let data = Vec::from(data);
                    Ok((address, data))
                })
                .collect()
        } else {
            Ok(Vec::with_capacity(0))
        };

        if update_vec.is_err() {
            return update_vec.unwrap_err();
        }

        update_vec.unwrap().into_iter().collect()
    };

    let deletes: Result<Vec<String>, ErrorCode> = if deletes_len > 0 {
        slice::from_raw_parts(deletes, deletes_len)
            .iter()
            .map(|c_str| {
                CStr::from_ptr(*c_str)
                    .to_str()
                    .map(String::from)
                    .map_err(|_| ErrorCode::InvalidAddress)
            })
            .collect()
    } else {
        Ok(Vec::with_capacity(0))
    };

    if deletes.is_err() {
        return deletes.unwrap_err();
    }

    match (*(merkle_db as *mut MerkleDatabase)).update(
        &update_map,
        &deletes.unwrap(),
        virtual_write,
    ) {
        Ok(state_root) => {
            *merkle_root_cap = state_root.capacity();
            *merkle_root_len = state_root.len();
            *merkle_root = state_root.as_str().as_ptr();

            mem::forget(state_root);

            ErrorCode::Success
        }
        Err(StateDatabaseError::NotFound(addr)) => {
            error!(
                "Address {}, in {}, was not found.",
                addr,
                if update_map.contains_key(&addr) {
                    "updates"
                } else {
                    "deletions"
                }
            );
            ErrorCode::NotFound
        }
        Err(StateDatabaseError::DatabaseError(err)) => {
            error!("A Database Error occurred: {}", err);
            ErrorCode::DatabaseError
        }
        Err(err) => {
            error!("Unknown Error!: {:?}", err);
            ErrorCode::Unknown
        }
    }
}

#[no_mangle]
pub unsafe extern "C" fn merkle_db_prune(
    state_database: *mut c_void,
    root: *const c_char,
    result: *mut bool,
) -> ErrorCode {
    if state_database.is_null() {
        return ErrorCode::NullPointerProvided;
    }
    if root.is_null() {
        return ErrorCode::NullPointerProvided;
    }

    let state_root = match CStr::from_ptr(root).to_str() {
        Ok(s) => s,
        Err(_) => return ErrorCode::InvalidHashString,
    };

    let db_ref = (state_database as *const LmdbDatabase).as_ref().unwrap();

    match MerkleDatabase::prune(db_ref, &state_root) {
        Ok(results) => {
            *result = !results.is_empty();
            ErrorCode::Success
        }
        Err(StateDatabaseError::InvalidHash(_)) => ErrorCode::InvalidHashString,
        Err(StateDatabaseError::InvalidChangeLogIndex(msg)) => {
            error!(
                "Invalid Change Log Index while pruning {}: {}",
                state_root, msg
            );
            ErrorCode::InvalidChangeLogIndex
        }
        Err(StateDatabaseError::DatabaseError(err)) => {
            error!("A Database Error occurred: {}", err);
            ErrorCode::DatabaseError
        }
        Err(err) => {
            error!("Unknown Error!: {:?}", err);
            ErrorCode::Unknown
        }
    }
}

#[no_mangle]
pub unsafe extern "C" fn merkle_db_leaf_iterator_new(
    merkle_db: *mut c_void,
    prefix: *const c_char,
    iterator: *mut *const c_void,
) -> ErrorCode {
    if merkle_db.is_null() {
        return ErrorCode::NullPointerProvided;
    }

    if prefix.is_null() {
        return ErrorCode::NullPointerProvided;
    }

    let prefix = match CStr::from_ptr(prefix).to_str() {
        Ok(s) => s,
        Err(_) => return ErrorCode::InvalidAddress,
    };

    match (*(merkle_db as *mut MerkleDatabase)).leaves(Some(prefix)) {
        Ok(leaf_iterator) => {
            *iterator = Box::into_raw(leaf_iterator) as *const c_void;

            ErrorCode::Success
        }
        Err(StateDatabaseError::DatabaseError(err)) => {
            error!("A Database Error occurred: {}", err);
            ErrorCode::DatabaseError
        }
        Err(StateDatabaseError::NotFound(_)) => ErrorCode::NotFound,
        Err(err) => {
            error!("Unknown Error!: {:?}", err);
            ErrorCode::Unknown
        }
    }
}

#[no_mangle]
pub unsafe extern "C" fn merkle_db_leaf_iterator_drop(iterator: *mut c_void) -> ErrorCode {
    if iterator.is_null() {
        return ErrorCode::NullPointerProvided;
    }

    Box::from_raw(iterator as *mut MerkleLeafIterator);
    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn merkle_db_leaf_iterator_next(
    iterator: *mut c_void,
    address: *mut *const u8,
    address_len: *mut usize,
    address_cap: *mut usize,
    bytes: *mut *const u8,
    bytes_len: *mut usize,
    bytes_cap: *mut usize,
) -> ErrorCode {
    if iterator.is_null() {
        return ErrorCode::NullPointerProvided;
    }

    match (*(iterator as *mut MerkleLeafIterator)).next() {
        Some(Ok((entry_addr, entry_bytes))) => {
            *address_cap = entry_addr.capacity();
            *address_len = entry_addr.len();
            *address = entry_addr.as_str().as_ptr();

            *bytes_cap = entry_bytes.capacity();
            *bytes_len = entry_bytes.len();
            *bytes = entry_bytes.as_slice().as_ptr();

            mem::forget(entry_addr);
            mem::forget(entry_bytes);

            ErrorCode::Success
        }
        None => ErrorCode::StopIteration,
        Some(Err(StateDatabaseError::DatabaseError(err))) => {
            error!("A Database Error occurred: {}", err);
            ErrorCode::DatabaseError
        }
        Some(Err(err)) => {
            error!("Unknown Error!: {:?}", err);
            ErrorCode::Unknown
        }
    }
}
