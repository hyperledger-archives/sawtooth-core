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

use std::env;
use std::path::{Path, PathBuf};

const DEFAULT_CONFIG_DIR: &str = "/etc/sawtooth";
const DEFAULT_LOG_DIR: &str = "/var/log/sawtooth";
const DEFAULT_DATA_DIR: &str = "/var/lib/sawtooth";
const DEFAULT_KEY_DIR: &str = "/etc/sawtooth/keys";
const DEFAULT_POLICY_DIR: &str = "/etc/sawtooth/policy";

const DEFAULT_BLOCKSTORE_FILENAME: &str = "block-00.lmdb";

pub struct PathConfig {
    pub config_dir: PathBuf,
    pub log_dir: PathBuf,
    pub data_dir: PathBuf,
    pub key_dir: PathBuf,
    pub policy_dir: PathBuf,
}

pub fn get_path_config() -> PathConfig {
    match env::var("SAWTOOTH_HOME") {
        Ok(prefix) => PathConfig {
            config_dir: Path::new(&prefix).join("etc").to_path_buf(),
            log_dir: Path::new(&prefix).join("logs").to_path_buf(),
            data_dir: Path::new(&prefix).join("data").to_path_buf(),
            key_dir: Path::new(&prefix).join("keys").to_path_buf(),
            policy_dir: Path::new(&prefix).join("policy").to_path_buf(),
        },
        Err(_) => PathConfig {
            config_dir: Path::new(DEFAULT_CONFIG_DIR).to_path_buf(),
            log_dir: Path::new(DEFAULT_LOG_DIR).to_path_buf(),
            data_dir: Path::new(DEFAULT_DATA_DIR).to_path_buf(),
            key_dir: Path::new(DEFAULT_KEY_DIR).to_path_buf(),
            policy_dir: Path::new(DEFAULT_POLICY_DIR).to_path_buf(),
        },
    }
}

pub fn get_blockstore_filename() -> String {
    String::from(DEFAULT_BLOCKSTORE_FILENAME)
}
