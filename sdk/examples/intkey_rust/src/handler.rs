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
use std::io::Cursor;
use std::fmt;

use cbor::encoder::GenericEncoder;
use cbor::value::Value;
use cbor::value::Key;
use cbor::value::Text;

use sawtooth_sdk::processor::handler::ApplyError;
use sawtooth_sdk::processor::handler::TransactionContext;
use sawtooth_sdk::processor::handler::TransactionHandler;
use sawtooth_sdk::messages::processor::TpProcessRequest;

#[derive(Copy, Clone)]
enum Verb {
    Set,
    Increment,
    Decrement
}

impl fmt::Display for Verb {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(f, "{}", match *self {
            Verb::Set => "Verb::Set",
            Verb::Increment => "Verb::Increment",
            Verb::Decrement => "Verb::Decrement",
        })
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
    value: u32
}

impl IntkeyPayload {
    pub fn new(payload_data: &[u8]) -> IntkeyPayload {
        let input = Cursor::new(payload_data);
        let mut decoder = cbor::GenericDecoder::new(cbor::Config::default(), input);
        let value = decoder.value().unwrap();
        let c = cbor::value::Cursor::new(&value);

        let verb_raw: &str = &c.field("Verb").text_plain().unwrap().clone();
        let verb = match verb_raw {
            "set" => Verb::Set,
            "inc" => Verb::Increment,
            "dec" => Verb::Decrement,
            _ => panic!("invalid")
        };

        let value: u32 = match c.field("Value").value().unwrap() {
            &cbor::value::Value::U8(x) => x as u32,
            &cbor::value::Value::U16(x) => x as u32,
            &cbor::value::Value::U32(x) => x,
            _ => panic!("invalid Value")
        };

        IntkeyPayload {
            verb: verb,
            name: c.field("Name").text_plain().unwrap().clone(),
            value: value
        }
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
    context: &'a mut TransactionContext
}

impl<'a> IntkeyState<'a> {
    pub fn new(context: &'a mut TransactionContext) -> IntkeyState {
        IntkeyState {
            context: context
        }
    }

    fn calculate_address(name: &str) -> String {
        let mut sha = Sha512::new();
        sha.input(name.as_bytes());
        get_intkey_prefix() + &sha.result_str()[64..].to_string()
    }

    pub fn get(&mut self, name: &str) -> Result<Option<u32>, ApplyError> {
        let d = self.context.get_state(&IntkeyState::calculate_address(name))?;
        match d {
            Some(packed) => {
                let input = Cursor::new(packed);
                let mut decoder = cbor::GenericDecoder::new(cbor::Config::default(), input);

                let map = match decoder.value().unwrap() {
                    Value::Map(m) => m,
                    _ => return Err(ApplyError::InternalError(String::from("error unhandled")))
                };

                match map.get(&Key::Text(Text::Text(String::from(name)))) {
                    Some(v) => match v {
                        &Value::U32(x) => Ok(Some(x)),
                        &Value::U16(x) => Ok(Some(x as u32)),
                        &Value::U8(x) => Ok(Some(x as u32)),
                        _ => Err(ApplyError::InternalError(String::from("error unhandled")))
                    },
                    None => Ok(None)
                }
            }
            None => Ok(None)
        }
    }

    pub fn set(&mut self, name: &str, value: u32) -> Result<(), ApplyError> {
        let d = self.context.get_state(&IntkeyState::calculate_address(name))?;
        let mut map = match d {
            Some(packed) => {
                let input = Cursor::new(packed);
                let mut decoder = cbor::GenericDecoder::new(cbor::Config::default(), input);

                match decoder.value().unwrap() {
                    Value::Map(m) => m,
                    _ => return Err(ApplyError::InternalError(String::from("error unhandled")))
                }
            }
            None => BTreeMap::new()
        };

        map.insert(Key::Text(Text::Text(String::from(name))), Value::U32(value));

        let mut e = GenericEncoder::new(Cursor::new(Vec::new()));
        e.value(&Value::Map(map)).unwrap();

        let packed = e.into_inner().into_writer().into_inner();

        self.context.set_state(&IntkeyState::calculate_address(name), &packed)?;

        Ok(())
    }
}

pub struct IntkeyTransactionHandler {
    family_name: String,
    family_versions: Vec<String>,
    namespaces: Vec<String>
}

impl IntkeyTransactionHandler {
    pub fn new() -> IntkeyTransactionHandler {
        IntkeyTransactionHandler {
            family_name: "intkey".to_string(),
            family_versions: vec!["1.0".to_string()],
            namespaces: vec![get_intkey_prefix().to_string()]
        }
    }
}

impl TransactionHandler for IntkeyTransactionHandler {
    fn family_name(&self) -> String {
        return self.family_name.clone()
    }

    fn family_versions(&self) -> Vec<String> {
        return self.family_versions.clone()
    }

    fn namespaces(&self) -> Vec<String> {
        return self.namespaces.clone()
    }

    fn apply(&self, request: &TpProcessRequest, context: &mut TransactionContext) -> Result<(), ApplyError> {
        let payload = IntkeyPayload::new(request.get_payload());
        let mut state = IntkeyState::new(context);

        info!("payload: {} {} {} {} {}",
              payload.get_verb(),
              payload.get_name(),
              payload.get_value(),
              request.get_header().get_inputs()[0],
              request.get_header().get_outputs()[0]);

        match payload.get_verb() {
            Verb::Set => {
                state.set(&payload.get_name(), payload.get_value())
            },
            Verb::Increment => {
                let orig_value: u32 = match state.get(payload.get_name()) {
                    Ok(Some(v)) => v,
                    Ok(None) => return Err(ApplyError::InvalidTransaction(String::from("inc requires a set value"))),
                    Err(err) => return Err(err)
                };
                state.set(&payload.get_name(), orig_value + payload.get_value())
            },
            Verb::Decrement => {
                let orig_value: u32 = match state.get(payload.get_name()) {
                    Ok(Some(v)) => v,
                    Ok(None) => return Err(ApplyError::InvalidTransaction(String::from("dec requires a set value"))),
                    Err(err) => return Err(err)
                };
                state.set(&payload.get_name(), orig_value - payload.get_value())
            }
        }
    }
}
