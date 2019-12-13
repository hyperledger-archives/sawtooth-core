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
use std::ffi::CStr;
use std::mem;
use std::os::raw::{c_char, c_void};
use std::slice;

use protobuf;

use batch::Batch;
use block::Block;
use database::error::DatabaseError;
use database::lmdb::LmdbDatabase;
use journal::commit_store::{ByHeightDirection, CommitStore, CommitStoreByHeightIterator};
use proto;
use transaction::Transaction;

#[repr(u32)]
#[derive(Debug)]
pub enum ErrorCode {
    Success = 0,

    // Input errors
    NullPointerProvided = 0x01,
    InvalidArgument = 0x02,

    // output errors
    DatabaseError = 0x10,
    NotFound = 0x11,

    StopIteration = 0x20,
}

macro_rules! check_null {
    ($($arg:expr) , *) => {
        $(if $arg.is_null() { return ErrorCode::NullPointerProvided; })*
    }
}

#[no_mangle]
pub unsafe extern "C" fn commit_store_new(
    database: *const c_void,
    commit_store: *mut *const c_void,
) -> ErrorCode {
    check_null!(database);
    let db_ref = (database as *const LmdbDatabase).as_ref().unwrap();
    let new_commit_store = CommitStore::new(db_ref.clone());
    *commit_store = Box::into_raw(Box::new(new_commit_store)) as *const c_void;
    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn commit_store_drop(commit_store: *mut c_void) -> ErrorCode {
    check_null!(commit_store);

    Box::from_raw(commit_store as *mut CommitStore);
    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn commit_store_get_by_block_id(
    commit_store: *mut c_void,
    block_id: *const c_char,
    block_ptr: *mut *const u8,
    block_len: *mut usize,
    block_cap: *mut usize,
) -> ErrorCode {
    check_null!(commit_store, block_id);

    match deref_cstr(block_id) {
        Ok(block_id) => match (*(commit_store as *mut CommitStore)).get_by_block_id(block_id) {
            Ok(block) => return_block(block, block_ptr, block_len, block_cap),
            Err(err) => map_database_error(err),
        },
        Err(err) => err,
    }
}

#[no_mangle]
pub unsafe extern "C" fn commit_store_get_chain_head(
    commit_store: *mut c_void,
    block_ptr: *mut *const u8,
    block_len: *mut usize,
    block_cap: *mut usize,
) -> ErrorCode {
    check_null!(commit_store);

    match (*(commit_store as *mut CommitStore)).get_chain_head() {
        Ok(block) => return_block(block, block_ptr, block_len, block_cap),
        Err(err) => map_database_error(err),
    }
}

#[no_mangle]
pub unsafe extern "C" fn commit_store_get_by_batch_id(
    commit_store: *mut c_void,
    batch_id: *const c_char,
    block_ptr: *mut *const u8,
    block_len: *mut usize,
    block_cap: *mut usize,
) -> ErrorCode {
    check_null!(commit_store, batch_id);

    match deref_cstr(batch_id) {
        Ok(batch_id) => match (*(commit_store as *mut CommitStore)).get_by_batch_id(batch_id) {
            Ok(block) => return_block(block, block_ptr, block_len, block_cap),
            Err(err) => map_database_error(err),
        },
        Err(err) => err,
    }
}

#[no_mangle]
pub unsafe extern "C" fn commit_store_get_by_transaction_id(
    commit_store: *mut c_void,
    transaction_id: *const c_char,
    block_ptr: *mut *const u8,
    block_len: *mut usize,
    block_cap: *mut usize,
) -> ErrorCode {
    check_null!(commit_store, transaction_id);

    match deref_cstr(transaction_id) {
        Ok(transaction_id) => {
            match (*(commit_store as *mut CommitStore)).get_by_transaction_id(transaction_id) {
                Ok(block) => return_block(block, block_ptr, block_len, block_cap),
                Err(err) => map_database_error(err),
            }
        }
        Err(err) => err,
    }
}

#[no_mangle]
pub unsafe extern "C" fn commit_store_get_by_block_num(
    commit_store: *mut c_void,
    block_num: u64,
    block_ptr: *mut *const u8,
    block_len: *mut usize,
    block_cap: *mut usize,
) -> ErrorCode {
    check_null!(commit_store);

    match (*(commit_store as *mut CommitStore)).get_by_block_num(block_num) {
        Ok(block) => return_block(block, block_ptr, block_len, block_cap),
        Err(err) => map_database_error(err),
    }
}

#[no_mangle]
pub unsafe extern "C" fn commit_store_get_batch(
    commit_store: *mut c_void,
    batch_id: *const c_char,
    batch_ptr: *mut *const u8,
    batch_len: *mut usize,
    batch_cap: *mut usize,
) -> ErrorCode {
    check_null!(commit_store, batch_id);

    match deref_cstr(batch_id) {
        Ok(batch_id) => match (*(commit_store as *mut CommitStore)).get_batch(batch_id) {
            Ok(batch) => return_batch(batch, batch_ptr, batch_len, batch_cap),
            Err(err) => map_database_error(err),
        },
        Err(err) => err,
    }
}

#[no_mangle]
pub unsafe extern "C" fn commit_store_get_transaction(
    commit_store: *mut c_void,
    transaction_id: *const c_char,
    transaction_ptr: *mut *const u8,
    transaction_len: *mut usize,
    transaction_cap: *mut usize,
) -> ErrorCode {
    check_null!(commit_store, transaction_id);

    match deref_cstr(transaction_id) {
        Ok(transaction_id) => {
            match (*(commit_store as *mut CommitStore)).get_transaction(transaction_id) {
                Ok(transaction) => return_transaction(
                    transaction,
                    transaction_ptr,
                    transaction_len,
                    transaction_cap,
                ),
                Err(err) => map_database_error(err),
            }
        }
        Err(err) => err,
    }
}

#[no_mangle]
pub unsafe extern "C" fn commit_store_get_batch_by_transaction(
    commit_store: *mut c_void,
    transaction_id: *const c_char,
    batch_ptr: *mut *const u8,
    batch_len: *mut usize,
    batch_cap: *mut usize,
) -> ErrorCode {
    check_null!(commit_store, transaction_id);

    match deref_cstr(transaction_id) {
        Ok(transaction_id) => {
            match (*(commit_store as *mut CommitStore)).get_batch_by_transaction(transaction_id) {
                Ok(batch) => return_batch(batch, batch_ptr, batch_len, batch_cap),
                Err(err) => map_database_error(err),
            }
        }
        Err(err) => err,
    }
}

#[no_mangle]
pub unsafe extern "C" fn commit_store_contains_block(
    commit_store: *mut c_void,
    block_id: *const c_char,
    contains_ptr: *mut bool,
) -> ErrorCode {
    check_null!(commit_store, block_id);

    match deref_cstr(block_id) {
        Ok(block_id) => match (*(commit_store as *mut CommitStore)).contains_block(block_id) {
            Ok(contains) => {
                *contains_ptr = contains;
                ErrorCode::Success
            }
            Err(err) => map_database_error(err),
        },
        Err(err) => err,
    }
}

#[no_mangle]
pub unsafe extern "C" fn commit_store_contains_batch(
    commit_store: *mut c_void,
    batch_id: *const c_char,
    contains_ptr: *mut bool,
) -> ErrorCode {
    check_null!(commit_store, batch_id);

    match deref_cstr(batch_id) {
        Ok(batch_id) => match (*(commit_store as *mut CommitStore)).contains_batch(batch_id) {
            Ok(contains) => {
                *contains_ptr = contains;
                ErrorCode::Success
            }
            Err(err) => map_database_error(err),
        },
        Err(err) => err,
    }
}

#[no_mangle]
pub unsafe extern "C" fn commit_store_contains_transaction(
    commit_store: *mut c_void,
    transaction_id: *const c_char,
    contains_ptr: *mut bool,
) -> ErrorCode {
    check_null!(commit_store, transaction_id);

    match deref_cstr(transaction_id) {
        Ok(transaction_id) => {
            match (*(commit_store as *mut CommitStore)).contains_transaction(transaction_id) {
                Ok(contains) => {
                    *contains_ptr = contains;
                    ErrorCode::Success
                }
                Err(err) => map_database_error(err),
            }
        }
        Err(err) => err,
    }
}

#[no_mangle]
pub unsafe extern "C" fn commit_store_get_block_count(
    commit_store: *mut c_void,
    count_ptr: *mut usize,
) -> ErrorCode {
    check_null!(commit_store);

    match (*(commit_store as *mut CommitStore)).get_block_count() {
        Ok(count) => {
            *count_ptr = count;
            ErrorCode::Success
        }
        Err(err) => map_database_error(err),
    }
}

#[no_mangle]
pub unsafe extern "C" fn commit_store_get_batch_count(
    commit_store: *mut c_void,
    count_ptr: *mut usize,
) -> ErrorCode {
    check_null!(commit_store);

    match (*(commit_store as *mut CommitStore)).get_batch_count() {
        Ok(count) => {
            *count_ptr = count;
            ErrorCode::Success
        }
        Err(err) => map_database_error(err),
    }
}

#[no_mangle]
pub unsafe extern "C" fn commit_store_get_transaction_count(
    commit_store: *mut c_void,
    count_ptr: *mut usize,
) -> ErrorCode {
    check_null!(commit_store);

    match (*(commit_store as *mut CommitStore)).get_transaction_count() {
        Ok(count) => {
            *count_ptr = count;
            ErrorCode::Success
        }
        Err(err) => map_database_error(err),
    }
}

#[no_mangle]
pub unsafe extern "C" fn commit_store_get_block_iter(
    commit_store: *mut c_void,
    start_block_num: *const u64,
    decreasing: bool,
    block_iter_ptr: *mut *const c_void,
) -> ErrorCode {
    check_null!(commit_store);

    let start = if start_block_num.is_null() {
        None
    } else {
        Some(*start_block_num)
    };

    let direction = if decreasing {
        ByHeightDirection::Decreasing
    } else {
        ByHeightDirection::Increasing
    };

    let block_iter =
        (*(commit_store as *mut CommitStore)).get_block_by_height_iter(start, direction);
    *block_iter_ptr = Box::into_raw(Box::new(block_iter)) as *const c_void;
    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn commit_store_block_by_height_iter_next(
    block_iter_ptr: *mut c_void,
    block_ptr: *mut *const u8,
    block_len: *mut usize,
    block_cap: *mut usize,
) -> ErrorCode {
    check_null!(block_iter_ptr);

    if let Some(block) = (*(block_iter_ptr as *mut CommitStoreByHeightIterator)).next() {
        return_block(block, block_ptr, block_len, block_cap)
    } else {
        ErrorCode::StopIteration
    }
}

#[no_mangle]
pub unsafe extern "C" fn commit_store_block_by_height_iter_drop(
    block_iter_ptr: *mut c_void,
) -> ErrorCode {
    check_null!(block_iter_ptr);

    Box::from_raw(block_iter_ptr as *mut CommitStoreByHeightIterator);
    ErrorCode::Success
}

#[repr(C)]
#[derive(Debug)]
pub struct PutEntry {
    block_bytes: *mut u8,
    block_bytes_len: usize,
}

#[no_mangle]
pub unsafe extern "C" fn commit_store_put_blocks(
    commit_store: *mut c_void,
    blocks: *const *const c_void,
    blocks_len: usize,
) -> ErrorCode {
    check_null!(commit_store, blocks);

    let blocks_result: Result<Vec<Block>, ErrorCode> = slice::from_raw_parts(blocks, blocks_len)
        .into_iter()
        .map(|ptr| {
            let entry = *ptr as *const PutEntry;
            let payload = slice::from_raw_parts((*entry).block_bytes, (*entry).block_bytes_len);
            let proto_block: proto::block::Block =
                protobuf::parse_from_bytes(&payload).expect("Failed to parse proto Block bytes");

            Ok(Block::from(proto_block))
        })
        .collect();

    match blocks_result {
        Ok(blocks) => match (*(commit_store as *mut CommitStore)).put_blocks(blocks) {
            Ok(_) => ErrorCode::Success,
            Err(err) => {
                error!("Error putting blocks: {:?}", err);
                ErrorCode::DatabaseError
            }
        },
        Err(err) => {
            error!("Error deserializing blocks from FFI: {:?}", err);
            ErrorCode::InvalidArgument
        }
    }
}

// FFI Helpers

unsafe fn return_block(
    block: Block,
    block_ptr: *mut *const u8,
    block_len: *mut usize,
    block_cap: *mut usize,
) -> ErrorCode {
    return_proto::<_, proto::block::Block>(block, block_ptr, block_len, block_cap)
}

unsafe fn return_batch(
    batch: Batch,
    batch_ptr: *mut *const u8,
    batch_len: *mut usize,
    batch_cap: *mut usize,
) -> ErrorCode {
    return_proto::<_, proto::batch::Batch>(batch, batch_ptr, batch_len, batch_cap)
}

unsafe fn return_transaction(
    transaction: Transaction,
    transaction_ptr: *mut *const u8,
    transaction_len: *mut usize,
    transaction_cap: *mut usize,
) -> ErrorCode {
    return_proto::<_, proto::transaction::Transaction>(
        transaction,
        transaction_ptr,
        transaction_len,
        transaction_cap,
    )
}

unsafe fn return_proto<I, O: protobuf::Message + From<I>>(
    input: I,
    output_ptr: *mut *const u8,
    output_len: *mut usize,
    output_cap: *mut usize,
) -> ErrorCode {
    match O::from(input).write_to_bytes() {
        Ok(payload) => {
            *output_cap = payload.capacity();
            *output_len = payload.len();
            *output_ptr = payload.as_slice().as_ptr();

            mem::forget(payload);

            ErrorCode::Success
        }
        Err(err) => {
            warn!("Failed to serialize Block proto to bytes: {}", err);
            ErrorCode::DatabaseError
        }
    }
}

fn map_database_error(err: DatabaseError) -> ErrorCode {
    match err {
        DatabaseError::NotFoundError(_) => ErrorCode::NotFound,
        err => {
            error!("Database error: {:?}", err);
            ErrorCode::DatabaseError
        }
    }
}

unsafe fn deref_cstr<'a>(cstr: *const c_char) -> Result<&'a str, ErrorCode> {
    CStr::from_ptr(cstr)
        .to_str()
        .map_err(|_| ErrorCode::InvalidArgument)
}
