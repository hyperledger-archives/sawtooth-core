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

use std::os::raw::c_void;

use journal::chain_head_lock::ChainHeadLock;

#[repr(u32)]
#[derive(Debug)]
pub enum ErrorCode {
    Success = 0,
    NullPointerProvided = 0x01,
}

#[no_mangle]
pub extern "C" fn chain_head_lock_drop(chain_head_lock_ptr: *mut c_void) -> ErrorCode {
    if chain_head_lock_ptr.is_null() {
        return ErrorCode::NullPointerProvided;
    }
    unsafe {
        Box::from_raw(chain_head_lock_ptr as *mut ChainHeadLock);
    }
    ErrorCode::Success
}
