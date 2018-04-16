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

use crypto::digest::Digest;
use crypto::sha2::Sha512;

pub struct IntKeyAddresser {
    namespace: String,
    pub family_name: String,
    pub version: String,
}

impl IntKeyAddresser {
    pub fn new() -> IntKeyAddresser {
        let mut hasher = Sha512::new();
        hasher.input_str("intkey");

        IntKeyAddresser {
            namespace: hasher.result_str()[..6].to_string(),
            family_name: "intkey".to_string(),
            version: "1.0".to_string(),
        }
    }

    pub fn make_address(&self, name: &str) -> String {
        let prefix = self.namespace.clone();
        let mut hasher = Sha512::new();
        hasher.input(name.as_bytes());
        (prefix + &hasher.result_str()[64..]).to_string()
    }
}
