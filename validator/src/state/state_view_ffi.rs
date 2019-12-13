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
use std::os::raw::c_void;

use database::lmdb::LmdbDatabase;
use state::state_view_factory::StateViewFactory;

#[repr(u32)]
#[derive(Debug)]
pub enum ErrorCode {
    Success = 0,
    NullPointerProvided = 1,
    Unknown = 0xFF,
}

#[no_mangle]
pub unsafe extern "C" fn state_view_factory_new(
    database: *const c_void,
    state_view_factory: *mut *const c_void,
) -> ErrorCode {
    if database.is_null() {
        return ErrorCode::NullPointerProvided;
    }

    let db_ref = (database as *const LmdbDatabase).as_ref().unwrap();

    *state_view_factory =
        Box::into_raw(Box::new(StateViewFactory::new(db_ref.clone()))) as *const c_void;
    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn state_view_factory_drop(state_view_factory: *mut c_void) -> ErrorCode {
    if state_view_factory.is_null() {
        return ErrorCode::NullPointerProvided;
    }

    Box::from_raw(state_view_factory as *mut StateViewFactory);
    ErrorCode::Success
}
