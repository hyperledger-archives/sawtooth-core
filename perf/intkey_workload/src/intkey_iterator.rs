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

use std::collections::BTreeMap;
use std::collections::HashMap;

use cbor::value::Key;
use cbor::value::Text;
use cbor::value::Value;

use rand::Rng;
use rand::SeedableRng;
use rand::StdRng;

const HALF_MAX_VALUE: u32 = 2_147_483_647;
const INCS_AND_DECS_PER_SET: usize = 200_000;
const MAX_NAME_LEN: usize = 20;

/// IntKeyPayload is serialized as cbor as a map {"Verb": verb, "Name": name, "Value": value}
/// and, along with other information, sent to the validator in a Transaction.
pub struct IntKeyPayload {
    pub verb: String,
    pub name: String,
    pub value: u32,
}

impl IntKeyPayload {
    pub fn construct(&self) -> Value {
        let name = self.name.clone();
        let verb = self.verb.clone();
        let value = self.value;

        let mut map = BTreeMap::new();
        map.insert(
            wrap_in_cbor_key("Name".to_string()),
            wrap_in_cbor_value(name),
        );
        map.insert(
            wrap_in_cbor_key("Verb".to_string()),
            wrap_in_cbor_value(verb),
        );
        map.insert(
            wrap_in_cbor_key("Value".to_string()),
            wrap_in_cbor_value_u32(value),
        );
        Value::Map(map)
    }
}

pub struct IntKeyIterator {
    num_names: usize,
    invalid: f32,

    rng: StdRng,

    names: HashMap<String, u32>,
    incs_and_decs_per_set: u32,
    set_value: u32,
}

impl IntKeyIterator {
    pub fn new(num_names: usize, invalid: f32, seed: &[usize]) -> IntKeyIterator {
        IntKeyIterator {
            num_names: num_names,
            invalid: invalid,

            rng: SeedableRng::from_seed(seed),

            names: HashMap::new(),
            incs_and_decs_per_set: INCS_AND_DECS_PER_SET as u32,
            set_value: HALF_MAX_VALUE,
        }
    }

    fn gen_name(&mut self) -> String {
        self.rng.gen_ascii_chars().take(MAX_NAME_LEN).collect()
    }

    /// Generate a RNG chosen inc or dec payload with the name supplied if not None,
    /// else if name is None, choose a random name.
    fn gen_inc_or_dec(&mut self, name: Option<String>) -> IntKeyPayload {
        let verb = if self.rng.gen::<bool>() { "inc" } else { "dec" };

        IntKeyPayload {
            name: name.unwrap_or_else(|| self.gen_name()),
            verb: verb.to_string(),
            value: self.rng.gen_range(1, 10),
        }
    }
}

impl Iterator for IntKeyIterator {
    type Item = IntKeyPayload;

    /// First use RNG to choose between invalid and valid txn.
    /// If valid, determine if there have been enough sets. If so choose between inc or dec.
    /// If not generate a random name to set.
    fn next(&mut self) -> Option<Self::Item> {
        if self.rng.gen_range(0.0, 1.0) >= self.invalid {
            // Valid transaction
            if self.names.len() < self.num_names {
                let name = self.gen_name();
                self.names.insert(name.clone(), 0);
                Some(IntKeyPayload {
                    name: name,
                    verb: "set".to_string(),
                    value: self.set_value,
                })
            } else {
                let names_map_clone = self.names.clone();
                let index = self.rng.gen_range(0, self.names.len());
                let name = names_map_clone
                    .keys()
                    .nth(index)
                    .expect("There is an indexing bug in the intkey iterator");

                let value = self
                    .names
                    .get(name)
                    .expect("There is an indexing bug in the intkey iterator")
                    .to_owned();

                if value < self.incs_and_decs_per_set {
                    self.names.insert(name.to_string(), value + 1);
                } else {
                    self.names.remove(name);
                }
                Some(self.gen_inc_or_dec(Some(name.to_string())))
            }
        } else {
            // invalid transaction

            Some(IntKeyPayload {
                name: self.gen_name(),
                verb: "invalid".to_string(),
                value: 0,
            })
        }
    }
}

fn wrap_in_cbor_key(key: String) -> Key {
    Key::Text(Text::Text(key))
}

fn wrap_in_cbor_value(value: String) -> Value {
    Value::Text(Text::Text(value))
}

fn wrap_in_cbor_value_u32(value: u32) -> Value {
    Value::U32(value)
}

#[cfg(test)]
mod tests {
    use super::IntKeyIterator;
    use super::HALF_MAX_VALUE;
    use super::INCS_AND_DECS_PER_SET;

    const MAX_VALUE: u32 = 4_294_967_295;

    #[test]
    fn test_sets_incs_and_decs() {
        let mut intkey_iterator =
            IntKeyIterator::new(2, 0.0, &[2, 3, 45, 95, 18, 81, 222, 2, 252, 2, 45]);

        let payload1 = intkey_iterator.next();
        assert!(payload1.is_some());
        assert!(payload1.unwrap().verb.as_str() == "set");

        let payload2 = intkey_iterator.next();
        assert!(payload2.is_some());
        assert!(payload2.unwrap().verb.as_str() == "set");

        let payload3 = intkey_iterator.next();
        assert!(payload3.is_some());
        assert!(vec!["inc", "dec"].contains(&payload3.unwrap().verb.as_ref()));

        assert!(
            intkey_iterator
                .take(INCS_AND_DECS_PER_SET)
                .fold(HALF_MAX_VALUE, |acc, p| if p.verb == "inc".to_string() {
                    acc + p.value
                } else if p.verb == "dec".to_string() {
                    acc - p.value
                } else {
                    acc
                })
                < MAX_VALUE
        );
    }

    #[test]
    fn test_invalid() {
        let intkey_iterator =
            IntKeyIterator::new(2, 1.0, &[2, 3, 45, 95, 18, 81, 222, 2, 252, 2, 45]);

        assert!(
            intkey_iterator
                .take(INCS_AND_DECS_PER_SET)
                .fold(0, |acc, p| if p.verb == "invalid".to_string() {
                    acc + 1
                } else {
                    acc
                })
                == INCS_AND_DECS_PER_SET
        );
    }
}
