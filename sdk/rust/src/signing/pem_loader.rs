/*
 * Copyright 2017 Intel Corporation
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

mod ffi {
    extern crate libc;
    use self::libc::{size_t, c_int, c_char};

    #[link(name = "loader")]
    extern {
        pub fn load_pem_key(pemstr: *mut c_char, pemstr_len: size_t, password: *mut c_char,
                            out_priv_key: *mut c_char, out_pub_key: *mut c_char) -> c_int;
    }

}
use std::ffi::CString;
use super::Error;


pub fn load_pem_key(pemstr: &str, password: &str) -> Result<(String, String), Error> {
    let c_pemstr = CString::new(pemstr).unwrap();
    let c_password = CString::new(password).unwrap();
    let pemstr_len = pemstr.len();
    let mut c_out_priv_key = CString::new("-----------------------------------------------------------------").unwrap();
    let mut c_out_pub_key = CString::new("-----------------------------------------------------------------------------------------------------------------------------------").unwrap();

    let err_num = unsafe {
        let c_ptr_pemstr = c_pemstr.into_raw();
        let c_ptr_password = c_password.into_raw();
        let c_ptr_out_priv_key = c_out_priv_key.into_raw();
        let c_ptr_out_pub_key = c_out_pub_key.into_raw();

        let err_num = ffi::load_pem_key(c_ptr_pemstr, pemstr_len, c_ptr_password,
            c_ptr_out_priv_key, c_ptr_out_pub_key);

        // Need to take back ownership of all pointers to avoid memory leak
        let _ = CString::from_raw(c_ptr_pemstr);
        let _ = CString::from_raw(c_ptr_password);

        // Need to return these
        c_out_priv_key = CString::from_raw(c_ptr_out_priv_key);
        c_out_pub_key = CString::from_raw(c_ptr_out_pub_key);

        err_num
    };

    match err_num {
        -1 => Err(Error::ParseError(String::from("Failed to decrypt or decode private key"))),
        -2 => Err(Error::ParseError(String::from("Failed to create new big number context"))),
        -3 => Err(Error::ParseError(String::from("Failed to load group"))),
        -4 => Err(Error::ParseError(String::from("Failed to load private key"))),
        -5 => Err(Error::ParseError(String::from("Failed to load public key point"))),
        -6 => Err(Error::ParseError(String::from("Failed to construct public key from point"))),
        _ => {
            let priv_key = c_out_priv_key.into_string().map_err(|_|
                Error::ParseError(String::from("FFI Error")))?;
            let pub_key = c_out_pub_key.into_string().map_err(|_|
                Error::ParseError(String::from("FFI Error")))?;
            Ok((priv_key, pub_key))
        }
    }
}
