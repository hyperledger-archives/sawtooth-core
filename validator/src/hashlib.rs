/*
 * Copyright 2018 Cargill Incorporated
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

use hex;
use openssl;

pub fn sha256_digest_str(item: &str) -> String {
    hex::encode(openssl::sha::sha256(item.as_bytes()))
}

pub fn sha256_digest_strs(strs: &[&str]) -> Vec<u8> {
    let mut hasher = openssl::sha::Sha256::new();
    for item in strs {
        hasher.update(item.as_bytes());
    }
    let mut bytes = Vec::new();
    bytes.extend(hasher.finish().iter());
    bytes
}

pub fn sha512_digest_bytes(item: &[u8]) -> Vec<u8> {
    let mut bytes: Vec<u8> = Vec::new();
    bytes.extend(openssl::sha::sha512(item).iter());
    bytes
}
