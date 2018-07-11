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
pub extern "C" fn merkle_db_new(
    database: *const c_void,
    merkle_db: *mut *const c_void,
) -> ErrorCode {
    make_merkle_db(database, None, merkle_db)
}

#[no_mangle]
pub extern "C" fn merkle_db_new_with_root(
    database: *const c_void,
    root: *const c_char,
    merkle_db: *mut *const c_void,
) -> ErrorCode {
    if root.is_null() {
        return ErrorCode::NullPointerProvided;
    }

    let state_root = unsafe {
        match CStr::from_ptr(root).to_str() {
            Ok(s) => Some(s),
            Err(_) => return ErrorCode::InvalidHashString,
        }
    };

    make_merkle_db(database, state_root, merkle_db)
}

fn make_merkle_db(
    database: *const c_void,
    root: Option<&str>,
    merkle_db: *mut *const c_void,
) -> ErrorCode {
    if database.is_null() {
        return ErrorCode::NullPointerProvided;
    }

    let db_ref = unsafe { (database as *const LmdbDatabase).as_ref().unwrap() };
    match MerkleDatabase::new(db_ref.clone(), root) {
        Ok(new_merkle_tree) => {
            unsafe {
                *merkle_db = Box::into_raw(Box::new(new_merkle_tree)) as *const c_void;
            }
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
pub extern "C" fn merkle_db_drop(merkle_db: *mut c_void) -> ErrorCode {
    if merkle_db.is_null() {
        return ErrorCode::NullPointerProvided;
    }

    unsafe { Box::from_raw(merkle_db as *mut MerkleDatabase) };
    ErrorCode::Success
}

#[no_mangle]
pub extern "C" fn merkle_db_get_merkle_root(
    merkle_db: *mut c_void,
    merkle_root: *mut *const u8,
    merkle_root_len: *mut usize,
) -> ErrorCode {
    if merkle_db.is_null() {
        return ErrorCode::NullPointerProvided;
    }

    unsafe {
        let state_root = (*(merkle_db as *mut MerkleDatabase)).get_merkle_root();
        *merkle_root = state_root.as_ptr();
        *merkle_root_len = state_root.as_bytes().len();

        mem::forget(state_root);

        ErrorCode::Success
    }
}

#[no_mangle]
pub extern "C" fn merkle_db_set_merkle_root(
    merkle_db: *mut c_void,
    root: *const c_char,
) -> ErrorCode {
    if merkle_db.is_null() {
        return ErrorCode::NullPointerProvided;
    }
    if root.is_null() {
        return ErrorCode::NullPointerProvided;
    }

    let state_root = unsafe {
        match CStr::from_ptr(root).to_str() {
            Ok(s) => s,
            Err(_) => return ErrorCode::InvalidHashString,
        }
    };

    match unsafe { (*(merkle_db as *mut MerkleDatabase)).set_merkle_root(state_root) } {
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
pub extern "C" fn merkle_db_contains(merkle_db: *mut c_void, address: *const c_char) -> ErrorCode {
    if merkle_db.is_null() {
        return ErrorCode::NullPointerProvided;
    }
    if address.is_null() {
        return ErrorCode::NullPointerProvided;
    }

    let address_str = unsafe {
        match CStr::from_ptr(address).to_str() {
            Ok(s) => s,
            Err(_) => return ErrorCode::InvalidAddress,
        }
    };

    unsafe {
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
}

#[no_mangle]
pub extern "C" fn merkle_db_get(
    merkle_db: *mut c_void,
    address: *const c_char,
    bytes: *mut *const u8,
    bytes_len: *mut usize,
) -> ErrorCode {
    if merkle_db.is_null() {
        return ErrorCode::NullPointerProvided;
    }
    if address.is_null() {
        return ErrorCode::NullPointerProvided;
    }

    let address_str = unsafe {
        match CStr::from_ptr(address).to_str() {
            Ok(s) => s,
            Err(_) => return ErrorCode::InvalidAddress,
        }
    };

    unsafe {
        match (*(merkle_db as *mut MerkleDatabase)).get(address_str) {
            Ok(Some(data_vec)) => {
                let data = data_vec.into_boxed_slice();
                *bytes_len = data.len();
                *bytes = data.as_ptr();

                // It will be up to the callee to cleanup this memory
                mem::forget(data);

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
}

#[no_mangle]
pub extern "C" fn merkle_db_set(
    merkle_db: *mut c_void,
    address: *const c_char,
    data: *const u8,
    data_len: usize,
    merkle_root: *mut *const u8,
    merkle_root_len: *mut usize,
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

    let address_str = unsafe {
        match CStr::from_ptr(address).to_str() {
            Ok(s) => s,
            Err(_) => return ErrorCode::InvalidHashString,
        }
    };

    let data = unsafe { slice::from_raw_parts(data, data_len) };

    unsafe {
        match (*(merkle_db as *mut MerkleDatabase)).set(address_str, data) {
            Ok(state_root) => {
                *merkle_root = state_root.as_ptr();
                *merkle_root_len = state_root.as_bytes().len();

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
}

#[no_mangle]
pub extern "C" fn merkle_db_delete(
    merkle_db: *mut c_void,
    address: *const c_char,
    merkle_root: *mut *const u8,
    merkle_root_len: *mut usize,
) -> ErrorCode {
    if merkle_db.is_null() {
        return ErrorCode::NullPointerProvided;
    }
    if address.is_null() {
        return ErrorCode::NullPointerProvided;
    }

    let address_str = unsafe {
        match CStr::from_ptr(address).to_str() {
            Ok(s) => s,
            Err(_) => return ErrorCode::InvalidHashString,
        }
    };

    unsafe {
        match (*(merkle_db as *mut MerkleDatabase)).delete(address_str) {
            Ok(state_root) => {
                *merkle_root = state_root.as_ptr();
                *merkle_root_len = state_root.as_bytes().len();

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
}

#[no_mangle]
pub extern "C" fn merkle_db_update(
    merkle_db: *mut c_void,
    updates: *const *const c_void,
    updates_len: usize,
    deletes: *const *const c_char,
    deletes_len: usize,
    virtual_write: bool,
    merkle_root: *mut *const u8,
    merkle_root_len: *mut usize,
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
            unsafe { slice::from_raw_parts(updates, updates_len) }
                .iter()
                .map(|ptr| unsafe {
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
        unsafe { slice::from_raw_parts(deletes, deletes_len) }
            .iter()
            .map(|c_str| {
                unsafe { CStr::from_ptr(*c_str).to_str() }
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

    unsafe {
        match (*(merkle_db as *mut MerkleDatabase)).update(
            &update_map,
            &deletes.unwrap(),
            virtual_write,
        ) {
            Ok(state_root) => {
                *merkle_root = state_root.as_ptr();
                *merkle_root_len = state_root.as_bytes().len();

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
}

#[no_mangle]
pub extern "C" fn merkle_db_prune(
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

    let state_root = unsafe {
        match CStr::from_ptr(root).to_str() {
            Ok(s) => s,
            Err(_) => return ErrorCode::InvalidHashString,
        }
    };

    let db_ref = unsafe { (state_database as *const LmdbDatabase).as_ref().unwrap() };

    match MerkleDatabase::prune(db_ref, &state_root) {
        Ok(results) => {
            unsafe {
                *result = !results.is_empty();
            }
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
pub extern "C" fn merkle_db_leaf_iterator_new(
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

    let prefix = unsafe {
        match CStr::from_ptr(prefix).to_str() {
            Ok(s) => s,
            Err(_) => return ErrorCode::InvalidAddress,
        }
    };

    match unsafe { (*(merkle_db as *mut MerkleDatabase)).leaves(Some(prefix)) } {
        Ok(leaf_iterator) => {
            unsafe {
                *iterator = Box::into_raw(leaf_iterator) as *const c_void;
            }

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
pub extern "C" fn merkle_db_leaf_iterator_drop(iterator: *mut c_void) -> ErrorCode {
    if iterator.is_null() {
        return ErrorCode::NullPointerProvided;
    }

    unsafe { Box::from_raw(iterator as *mut MerkleLeafIterator) };
    ErrorCode::Success
}

#[no_mangle]
pub extern "C" fn merkle_db_leaf_iterator_next(
    iterator: *mut c_void,
    address: *mut *const u8,
    address_len: *mut usize,
    bytes: *mut *const u8,
    bytes_len: *mut usize,
) -> ErrorCode {
    if iterator.is_null() {
        return ErrorCode::NullPointerProvided;
    }

    match unsafe { (*(iterator as *mut MerkleLeafIterator)).next() } {
        Some(Ok((entry_addr, entry_bytes))) => unsafe {
            let address_bytes = entry_addr.into_bytes().into_boxed_slice();
            *address_len = address_bytes.len();
            *address = address_bytes.as_ptr();

            let data = entry_bytes.into_boxed_slice();
            *bytes_len = data.len();
            *bytes = data.as_ptr();

            mem::forget(address_bytes);
            mem::forget(data);

            ErrorCode::Success
        },
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
