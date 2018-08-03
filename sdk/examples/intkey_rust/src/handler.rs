/*
 * Copyright 2017 Bitwise IO, Inc.
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
 * -----------------------------------------------------------------------------
 */

use cbor;

use crypto::digest::Digest;
use crypto::sha2::Sha512;

use std::collections::BTreeMap;
use std::collections::HashMap;
use std::fmt;
use std::io::Cursor;

use cbor::encoder::GenericEncoder;
use cbor::value::Key;
use cbor::value::Text;
use cbor::value::Value;

use sawtooth_sdk::messages::processor::TpProcessRequest;
use sawtooth_sdk::processor::handler::ApplyError;
use sawtooth_sdk::processor::handler::TransactionContext;
use sawtooth_sdk::processor::handler::TransactionHandler;

const MAX_VALUE: u32 = 4_294_967_295;
const MAX_NAME_LEN: usize = 20;

#[derive(Copy, Clone)]
enum Verb {
    Set,
    Increment,
    Decrement,
}

impl fmt::Display for Verb {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(
            f,
            "{}",
            match *self {
                Verb::Set => "Verb::Set",
                Verb::Increment => "Verb::Increment",
                Verb::Decrement => "Verb::Decrement",
            }
        )
    }
}

fn get_intkey_prefix() -> String {
    let mut sha = Sha512::new();
    sha.input_str("intkey");
    sha.result_str()[..6].to_string()
}

struct IntkeyPayload {
    verb: Verb,
    name: String,
    value: u32,
}

impl IntkeyPayload {
    pub fn new(payload_data: &[u8]) -> Result<Option<IntkeyPayload>, ApplyError> {
        let input = Cursor::new(payload_data);

        let mut decoder = cbor::GenericDecoder::new(cbor::Config::default(), input);
        let decoder_value = decoder
            .value()
            .map_err(|err| ApplyError::InternalError(format!("{}", err)))?;

        let c = cbor::value::Cursor::new(&decoder_value);

        let verb_raw: String = match c.field("Verb").text_plain() {
            None => {
                return Err(ApplyError::InvalidTransaction(String::from(
                    "Verb must be 'set', 'inc', or 'dec'",
                )))
            }
            Some(verb_raw) => verb_raw.clone(),
        };

        let verb = match verb_raw.as_str() {
            "set" => Verb::Set,
            "inc" => Verb::Increment,
            "dec" => Verb::Decrement,
            _ => {
                return Err(ApplyError::InvalidTransaction(String::from(
                    "Verb must be 'set', 'inc', or 'dec'",
                )))
            }
        };

        let value_raw = c.field("Value");
        let value_raw = match value_raw.value() {
            Some(x) => x,
            None => {
                return Err(ApplyError::InvalidTransaction(String::from(
                    "Must have a value",
                )))
            }
        };

        let value: u32 = match *value_raw {
            cbor::value::Value::U8(x) => u32::from(x),
            cbor::value::Value::U16(x) => u32::from(x),
            cbor::value::Value::U32(x) => x,
            _ => {
                return Err(ApplyError::InvalidTransaction(String::from(
                    "Value must be an integer",
                )))
            }
        };

        let name_raw: String = match c.field("Name").text_plain() {
            None => {
                return Err(ApplyError::InvalidTransaction(String::from(
                    "Name must be a string",
                )))
            }
            Some(name_raw) => name_raw.clone(),
        };

        if name_raw.len() > MAX_NAME_LEN {
            return Err(ApplyError::InvalidTransaction(String::from(
                "Name must be equal to or less than 20 characters",
            )));
        }

        let intkey_payload = IntkeyPayload {
            verb: verb,
            name: name_raw,
            value: value,
        };
        Ok(Some(intkey_payload))
    }

    pub fn get_verb(&self) -> Verb {
        self.verb
    }

    pub fn get_name(&self) -> &String {
        &self.name
    }

    pub fn get_value(&self) -> u32 {
        self.value
    }
}

pub struct IntkeyState<'a> {
    context: &'a mut TransactionContext,
    get_cache: HashMap<String, BTreeMap<Key, Value>>,
}

impl<'a> IntkeyState<'a> {
    pub fn new(context: &'a mut TransactionContext) -> IntkeyState {
        IntkeyState {
            context: context,
            get_cache: HashMap::new(),
        }
    }

    fn calculate_address(name: &str) -> String {
        let mut sha = Sha512::new();
        sha.input(name.as_bytes());
        get_intkey_prefix() + &sha.result_str()[64..].to_string()
    }

    pub fn get(&mut self, name: &str) -> Result<Option<u32>, ApplyError> {
        let address = IntkeyState::calculate_address(name);
        let d = self.context.get_state(vec![address.clone()])?;
        match d {
            Some(packed) => {
                let input = Cursor::new(packed);
                let mut decoder = cbor::GenericDecoder::new(cbor::Config::default(), input);
                let map_value = decoder
                    .value()
                    .map_err(|err| ApplyError::InternalError(format!("{}", err)))?;
                let mut map = match map_value {
                    Value::Map(m) => m,
                    _ => {
                        return Err(ApplyError::InternalError(String::from(
                            "No map returned from state",
                        )))
                    }
                };

                let status = match map.get(&Key::Text(Text::Text(String::from(name)))) {
                    Some(v) => match *v {
                        Value::U32(x) => Ok(Some(x)),
                        Value::U16(x) => Ok(Some(u32::from(x))),
                        Value::U8(x) => Ok(Some(u32::from(x))),
                        _ => Err(ApplyError::InternalError(String::from(
                            "Value returned from state is the wrong type.",
                        ))),
                    },
                    None => Ok(None),
                };
                self.get_cache.insert(address.clone(), map.clone());
                status
            }
            None => Ok(None),
        }
    }

    pub fn set(&mut self, name: &str, value: u32) -> Result<(), ApplyError> {
        let mut map: BTreeMap<Key, Value> = match self
            .get_cache
            .get_mut(&IntkeyState::calculate_address(name))
        {
            Some(m) => m.clone(),
            None => BTreeMap::new(),
        };
        map.insert(Key::Text(Text::Text(String::from(name))), Value::U32(value));

        let mut e = GenericEncoder::new(Cursor::new(Vec::new()));
        e.value(&Value::Map(map))
            .map_err(|err| ApplyError::InternalError(format!("{}", err)))?;

        let packed = e.into_inner().into_writer().into_inner();
        let mut sets = HashMap::new();
        sets.insert(IntkeyState::calculate_address(name), packed);
        self.context
            .set_state(sets)
            .map_err(|err| ApplyError::InternalError(format!("{}", err)))?;

        Ok(())
    }
}

pub struct IntkeyTransactionHandler {
    family_name: String,
    family_versions: Vec<String>,
    namespaces: Vec<String>,
}

impl IntkeyTransactionHandler {
    pub fn new() -> IntkeyTransactionHandler {
        IntkeyTransactionHandler {
            family_name: "intkey".to_string(),
            family_versions: vec!["1.0".to_string()],
            namespaces: vec![get_intkey_prefix().to_string()],
        }
    }
}

impl TransactionHandler for IntkeyTransactionHandler {
    fn family_name(&self) -> String {
        self.family_name.clone()
    }

    fn family_versions(&self) -> Vec<String> {
        self.family_versions.clone()
    }

    fn namespaces(&self) -> Vec<String> {
        self.namespaces.clone()
    }

    fn apply(
        &self,
        request: &TpProcessRequest,
        context: &mut TransactionContext,
    ) -> Result<(), ApplyError> {
        let payload = IntkeyPayload::new(request.get_payload());
        let payload = match payload {
            Err(e) => return Err(e),
            Ok(payload) => payload,
        };
        let payload = match payload {
            Some(x) => x,
            None => {
                return Err(ApplyError::InvalidTransaction(String::from(
                    "Request must contain a payload",
                )))
            }
        };

        let mut state = IntkeyState::new(context);

        info!(
            "payload: {} {} {} {} {}",
            payload.get_verb(),
            payload.get_name(),
            payload.get_value(),
            request.get_header().get_inputs()[0],
            request.get_header().get_outputs()[0]
        );

        match payload.get_verb() {
            Verb::Set => {
                match state.get(payload.get_name()) {
                    Ok(Some(_)) => {
                        return Err(ApplyError::InvalidTransaction(format!(
                            "{} already set",
                            payload.get_name()
                        )))
                    }
                    Ok(None) => (),
                    Err(err) => return Err(err),
                };
                state.set(&payload.get_name(), payload.get_value())
            }
            Verb::Increment => {
                let orig_value: u32 = match state.get(payload.get_name()) {
                    Ok(Some(v)) => v,
                    Ok(None) => {
                        return Err(ApplyError::InvalidTransaction(String::from(
                            "inc requires a set value",
                        )))
                    }
                    Err(err) => return Err(err),
                };
                let diff = MAX_VALUE - orig_value;
                if diff < payload.get_value() {
                    return Err(ApplyError::InvalidTransaction(String::from(
                        "Value is too large to inc",
                    )));
                };

                state.set(&payload.get_name(), orig_value + payload.get_value())
            }
            Verb::Decrement => {
                let orig_value: u32 = match state.get(payload.get_name()) {
                    Ok(Some(v)) => v,
                    Ok(None) => {
                        return Err(ApplyError::InvalidTransaction(String::from(
                            "dec requires a set value",
                        )))
                    }
                    Err(err) => return Err(err),
                };
                if payload.get_value() > orig_value {
                    return Err(ApplyError::InvalidTransaction(String::from(
                        "Value is too large to dec",
                    )));
                };
                state.set(&payload.get_name(), orig_value - payload.get_value())
            }
        }
    }
}
