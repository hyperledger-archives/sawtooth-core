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
