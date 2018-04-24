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
use database::lmdb::*;
use std::ffi::CStr;
use std::path::Path;
use std::os::raw::{c_char, c_void};

#[repr(u32)]
pub enum ErrorCode {
    Success = 0,
    NullPointerProvided = 0x01,
    InvalidFilePath = 0x02,

    InitializeContextError = 0x11,
    InitializeDatabaseError = 0x12,
}

#[no_mangle]
pub extern "C" fn lmdb_database_new(
    path: *const c_char,
    file_size: usize,
    db_ptr: *mut *const c_void,
) -> ErrorCode {
    if path.is_null() {
        return ErrorCode::NullPointerProvided;
    }

    let db_path = unsafe {
        match CStr::from_ptr(path).to_str() {
            Ok(s) => s,
            Err(_) => return ErrorCode::InvalidFilePath,
        }
    };

    // Note, no indexes are being specified yet
    let ctx = match LmdbContext::new(Path::new(&db_path), 1, Some(file_size)) {
        Ok(ctx) => ctx,
        Err(err) => {
            error!(
                "Unable to create LMDB context for db at {}: {:?}",
                db_path, err
            );
            return ErrorCode::InitializeContextError;
        }
    };

    match LmdbDatabase::new(ctx, &[]) {
        Ok(db) => {
            unsafe {
                *db_ptr = Box::into_raw(Box::new(db)) as *const c_void;
            }
            ErrorCode::Success
        }
        Err(err) => {
            error!("Unable to create Database at {}: {:?}", db_path, err);
            ErrorCode::InitializeDatabaseError
        }
    }
}

#[no_mangle]
pub extern "C" fn lmdb_database_drop(lmdb_database: *mut c_void) -> ErrorCode {
    if lmdb_database.is_null() {
        return ErrorCode::NullPointerProvided;
    }

    unsafe { Box::from_raw(lmdb_database as *mut LmdbDatabase) };
    ErrorCode::Success
}
