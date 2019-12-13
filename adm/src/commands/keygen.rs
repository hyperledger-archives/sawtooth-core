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

use std::ffi::CString;
use std::fs::{metadata, OpenOptions};
use std::io::prelude::*;
#[cfg(target_os = "linux")]
use std::os::linux::fs::MetadataExt;
#[cfg(not(target_os = "linux"))]
use std::os::unix::fs::MetadataExt;
use std::os::unix::fs::OpenOptionsExt;
use std::path::Path;

use clap::ArgMatches;
use libc;

use sawtooth_sdk::signing;

use config;
use err::CliError;

pub fn run<'a>(args: &ArgMatches<'a>) -> Result<(), CliError> {
    let path_config = config::get_path_config();
    let key_dir = &path_config.key_dir;
    if !key_dir.exists() {
        return Err(CliError::EnvironmentError(format!(
            "Key directory does not exist: {:?}",
            key_dir
        )));
    }

    let key_name = args.value_of("key_name").unwrap_or("validator");
    let private_key_path = key_dir.join(key_name).with_extension("priv");
    let public_key_path = key_dir.join(key_name).with_extension("pub");

    if !args.is_present("force") {
        if private_key_path.exists() {
            return Err(CliError::EnvironmentError(format!(
                "file exists: {:?}",
                private_key_path
            )));
        }
        if public_key_path.exists() {
            return Err(CliError::EnvironmentError(format!(
                "file exists: {:?}",
                public_key_path
            )));
        }
    }

    let context = signing::create_context("secp256k1")
        .map_err(|err| CliError::EnvironmentError(format!("{}", err)))?;

    let private_key = context
        .new_random_private_key()
        .map_err(|err| CliError::EnvironmentError(format!("{}", err)))?;
    let public_key = context
        .get_public_key(&*private_key)
        .map_err(|err| CliError::EnvironmentError(format!("{}", err)))?;

    let key_dir_info =
        metadata(key_dir).map_err(|err| CliError::EnvironmentError(format!("{}", err)))?;

    #[cfg(not(target_os = "linux"))]
    let (key_dir_uid, key_dir_gid) = (key_dir_info.uid(), key_dir_info.gid());
    #[cfg(target_os = "linux")]
    let (key_dir_uid, key_dir_gid) = (key_dir_info.st_uid(), key_dir_info.st_gid());

    {
        if private_key_path.exists() {
            println!("overwriting file: {:?}", private_key_path);
        } else {
            println!("writing file: {:?}", private_key_path);
        }
        let mut private_key_file = OpenOptions::new()
            .write(true)
            .create(true)
            .mode(0o640)
            .open(private_key_path.as_path())
            .map_err(|err| CliError::EnvironmentError(format!("{}", err)))?;

        private_key_file
            .write(private_key.as_hex().as_bytes())
            .map_err(|err| CliError::EnvironmentError(format!("{}", err)))?;
    }

    {
        if public_key_path.exists() {
            println!("overwriting file: {:?}", public_key_path);
        } else {
            println!("writing file: {:?}", public_key_path);
        }
        let mut public_key_file = OpenOptions::new()
            .write(true)
            .create(true)
            .mode(0o644)
            .open(public_key_path.as_path())
            .map_err(|err| CliError::EnvironmentError(format!("{}", err)))?;

        public_key_file
            .write(public_key.as_hex().as_bytes())
            .map_err(|err| CliError::EnvironmentError(format!("{}", err)))?;
    }

    chown(private_key_path.as_path(), key_dir_uid, key_dir_gid)?;
    chown(public_key_path.as_path(), key_dir_uid, key_dir_gid)?;
    Ok(())
}

fn chown(path: &Path, uid: u32, gid: u32) -> Result<(), CliError> {
    let pathstr = path
        .to_str()
        .ok_or_else(|| CliError::EnvironmentError(format!("Invalid path: {:?}", path)))?;
    let cpath =
        CString::new(pathstr).map_err(|err| CliError::EnvironmentError(format!("{}", err)))?;
    let result = unsafe { libc::chown(cpath.as_ptr(), uid, gid) };
    match result {
        0 => Ok(()),
        code => Err(CliError::EnvironmentError(format!(
            "Error chowning file {}: {}",
            pathstr, code
        ))),
    }
}
