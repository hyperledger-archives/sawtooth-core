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
use std::cell::RefCell;
use std::collections::HashMap;
use std::iter::repeat;
use std::num::ParseIntError;

use hashlib::sha256_digest_str;
use protobuf;

use state::StateDatabaseError;
use state::StateReader;

use proto::setting::Setting;

const CONFIG_STATE_NAMESPACE: &str = "000000";
const MAX_KEY_PARTS: usize = 4;
const ADDRESS_PART_SIZE: usize = 16;

#[derive(Debug)]
pub enum SettingsViewError {
    StateDatabaseError(StateDatabaseError),
    EncodingError(protobuf::ProtobufError),

    ParseError(String),
    ParseIntError(ParseIntError),
    UnknownError,
}

impl From<StateDatabaseError> for SettingsViewError {
    fn from(err: StateDatabaseError) -> Self {
        SettingsViewError::StateDatabaseError(err)
    }
}

impl From<protobuf::ProtobufError> for SettingsViewError {
    fn from(err: protobuf::ProtobufError) -> Self {
        SettingsViewError::EncodingError(err)
    }
}

impl From<ParseIntError> for SettingsViewError {
    fn from(err: ParseIntError) -> Self {
        SettingsViewError::ParseIntError(err)
    }
}

pub struct SettingsView {
    state_reader: Box<StateReader>,
    cache: RefCell<HashMap<String, Option<String>>>,
}

// Given that this is not threadsafe, but can be members of objects that can
// be moved between threads (themselves guarded by mutexes/rwlocks), we can
// safely implement sync.
unsafe impl Sync for SettingsView {}

impl SettingsView {
    /// Creates a new SettingsView with a given StateReader
    pub fn new(state_reader: Box<StateReader>) -> Self {
        SettingsView {
            state_reader,
            cache: RefCell::new(HashMap::new()),
        }
    }

    pub fn get_setting_str(
        &self,
        key: &str,
        default_value: Option<String>,
    ) -> Result<Option<String>, SettingsViewError> {
        self.get_setting(key, default_value, |s: &str| Ok(s.to_string()))
    }

    pub fn get_setting_u32(
        &self,
        key: &str,
        default_value: Option<u32>,
    ) -> Result<Option<u32>, SettingsViewError> {
        self.get_setting(key, default_value, |value| {
            value.parse().map_err(SettingsViewError::ParseIntError)
        })
    }

    pub fn get_setting<T, F>(
        &self,
        key: &str,
        default_value: Option<T>,
        value_parser: F,
    ) -> Result<Option<T>, SettingsViewError>
    where
        F: FnOnce(&str) -> Result<T, SettingsViewError>,
    {
        {
            let cache = self.cache.borrow();
            if cache.contains_key(key) {
                return if let Some(str_value) = cache.get(key).unwrap() {
                    Ok(Some(value_parser(&str_value)?))
                } else {
                    Ok(default_value)
                };
            }
        }
        let bytes_opt = match self.state_reader.get(&setting_address(key)) {
            Ok(opt) => opt,
            Err(StateDatabaseError::NotFound(_)) => return Ok(default_value),
            Err(err) => return Err(SettingsViewError::from(err)),
        };
        let setting_opt = if let Some(bytes) = bytes_opt {
            Some(protobuf::parse_from_bytes::<Setting>(&bytes)?)
        } else {
            None
        };

        let optional_str_value: Option<String> = setting_opt.and_then(|setting| {
            setting
                .get_entries()
                .iter()
                .find(|entry| entry.key == key)
                .map(|entry| entry.get_value().to_string())
        });

        {
            // cache it:
            let mut cache = self.cache.borrow_mut();
            cache.insert(key.to_string(), optional_str_value.clone());
        }

        if let Some(str_value) = optional_str_value.as_ref() {
            Ok(Some(value_parser(str_value)?))
        } else {
            Ok(default_value)
        }
    }
}

impl From<Box<StateReader>> for SettingsView {
    fn from(state_reader: Box<StateReader>) -> Self {
        SettingsView::new(state_reader)
    }
}

fn setting_address(key: &str) -> String {
    let mut address = String::new();
    address.push_str(CONFIG_STATE_NAMESPACE);
    address.push_str(
        &key.splitn(MAX_KEY_PARTS, '.')
            .chain(repeat(""))
            .map(short_hash)
            .take(MAX_KEY_PARTS)
            .collect::<Vec<_>>()
            .join(""),
    );

    address
}

fn short_hash(s: &str) -> String {
    sha256_digest_str(s)[..ADDRESS_PART_SIZE].to_string()
}

#[cfg(test)]
mod tests {
    use super::*;
    use proto::setting::Setting;
    use proto::setting::Setting_Entry;
    use protobuf;
    use protobuf::Message;
    use state::StateDatabaseError;
    use state::StateReader;
    use std::collections::HashMap;

    #[test]
    fn addresses() {
        // These addresses were generated via the python implementation
        assert_eq!(
            "000000ca978112ca1bbdca3e23e8160039594a2e7d2c03a9507ae2e3b0c44298fc1c14",
            setting_address("a.b.c")
        );
        assert_eq!(
            "000000ca978112ca1bbdca3e23e8160039594a2e7d2c03a9507ae2e67adc8234459dc2",
            setting_address("a.b.c.d.e")
        );
        assert_eq!(
            "000000a87cb5eafdcca6a8c983c585ac3c40d9b1eb2ec8ac9f31ffe3b0c44298fc1c14",
            setting_address("sawtooth.consensus.algorithm")
        );
    }

    #[test]
    fn basics() {
        let mock_reader = MockStateReader::new(vec![
            setting_entry("my.setting", "10"),
            setting_entry("my.setting.list", "10,11,12"),
            setting_entry("my.other.list", "13;14;15"),
        ]);

        let settings_view = SettingsView::new(Box::new(mock_reader));

        // Test not founds
        assert_eq!(
            None,
            settings_view
                .get_setting_str("some.nonexistent.setting", None)
                .unwrap()
        );
        assert_eq!(
            Some("default".to_string()),
            settings_view
                .get_setting_str("some.nonexistent.setting", Some("default".to_string()))
                .unwrap()
        );

        // return setting values
        assert_eq!(
            Some("10".to_string()),
            settings_view.get_setting_str("my.setting", None).unwrap()
        );
        assert_eq!(
            Some(10),
            settings_view.get_setting_u32("my.setting", None).unwrap()
        );

        // Test with advanced parsing
        assert_eq!(
            Some(vec![10, 11, 12]),
            settings_view
                .get_setting("my.setting.list", None, |value| value
                    .split(',')
                    .map(|s| s.parse().map_err(SettingsViewError::ParseIntError))
                    .collect::<Result<Vec<u32>, SettingsViewError>>())
                .unwrap()
        );

        assert_eq!(
            Some(vec![13, 14, 15]),
            settings_view
                .get_setting("my.other.list", None, |value| value
                    .split(';')
                    .map(|s| s.parse().map_err(SettingsViewError::ParseIntError))
                    .collect::<Result<Vec<u32>, SettingsViewError>>())
                .unwrap()
        );

        // Verify that we still return the default
        assert_eq!(
            Some(vec![]),
            settings_view
                .get_setting("some.nonexistent.setting", Some(vec![]), |value| value
                    .split(',')
                    .map(|s| s.parse().map_err(SettingsViewError::ParseIntError))
                    .collect::<Result<Vec<u32>, SettingsViewError>>())
                .unwrap()
        );
    }

    fn setting_entry(key: &str, value: &str) -> (String, Vec<u8>) {
        let mut setting = Setting::new();
        let mut setting_entry = Setting_Entry::new();
        setting_entry.set_key(key.into());
        setting_entry.set_value(value.into());

        setting.set_entries(protobuf::RepeatedField::from_vec(vec![setting_entry]));

        (
            setting_address(key),
            setting
                .write_to_bytes()
                .expect("Unable to serialize setting"),
        )
    }

    struct MockStateReader {
        state: HashMap<String, Vec<u8>>,
    }

    impl MockStateReader {
        fn new(values: Vec<(String, Vec<u8>)>) -> Self {
            MockStateReader {
                state: values.into_iter().collect(),
            }
        }
    }

    impl StateReader for MockStateReader {
        fn get(&self, address: &str) -> Result<Option<Vec<u8>>, StateDatabaseError> {
            match self.state.get(address).cloned() {
                Some(s) => Ok(Some(s)),
                None => Err(StateDatabaseError::NotFound(address.into())),
            }
        }

        fn contains(&self, address: &str) -> Result<bool, StateDatabaseError> {
            Ok(self.state.contains_key(address))
        }

        fn leaves(
            &self,
            prefix: Option<&str>,
        ) -> Result<
            Box<Iterator<Item = Result<(String, Vec<u8>), StateDatabaseError>>>,
            StateDatabaseError,
        > {
            let iterable: Vec<_> = self
                .state
                .iter()
                .filter(|(key, _)| key.starts_with(prefix.unwrap_or("")))
                .map(|(key, value)| Ok((key.clone().to_string(), value.clone())))
                .collect();

            Ok(Box::new(iterable.into_iter()))
        }
    }
}
