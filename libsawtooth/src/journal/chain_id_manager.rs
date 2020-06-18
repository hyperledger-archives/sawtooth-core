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
use std::fs::File;
use std::io;
use std::io::prelude::*;
use std::path::PathBuf;

/// The ChainIdManager is in charge of of keeping track of the block-chain-id
/// stored in the data_dir.
#[derive(Clone, Debug)]
pub struct ChainIdManager {
    data_dir: String,
}

impl ChainIdManager {
    pub fn new(data_dir: String) -> Self {
        ChainIdManager { data_dir }
    }

    pub fn save_block_chain_id(&self, block_chain_id: &str) -> Result<(), io::Error> {
        let mut path = PathBuf::new();
        path.push(&self.data_dir);
        path.push("block-chain-id");

        let mut file = File::create(path)?;
        file.write_all(block_chain_id.as_bytes())
    }

    pub fn get_block_chain_id(&self) -> Result<Option<String>, io::Error> {
        let mut path = PathBuf::new();
        path.push(&self.data_dir);
        path.push("block-chain-id");

        match File::open(path) {
            Ok(mut file) => {
                let mut contents = String::new();
                file.read_to_string(&mut contents)?;
                Ok(Some(contents))
            }
            Err(ref err) if err.kind() == io::ErrorKind::NotFound => Ok(None),
            Err(err) => Err(err),
        }
    }
}
