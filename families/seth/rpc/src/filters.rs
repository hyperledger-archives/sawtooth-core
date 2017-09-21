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

use jsonrpc_core::{Value, Error};

#[derive(Debug, PartialEq, Clone)]
pub enum Topic {
    Null,
    Data(String),
    Array(Vec<Topic>),
}

impl Topic {
    fn from_value(value: &Value) -> Self {
        match value {
            &Value::Array(ref array) =>
                Topic::Array(array.iter().map(|val| Topic::from_value(val)).collect()),
            &Value::String(ref data) => Topic::Data(data.clone()),
            &Value::Null => Topic::Null,
            _ => Topic::Null
        }
    }
}

#[derive(Debug, Clone)]
pub struct LogFilterSpec {
    from_block: String,
    to_block: String,
    addresses: Vec<String>,
    topics: Topic
}

impl LogFilterSpec {
    pub fn from_value(params: Value) -> Result<Self, Error> {
        let from_block = params.get(0)
            .and_then(|obj| obj.get("fromBlock"))
            .and_then(|s| s.as_str()).unwrap_or("latest");
        let to_block = params.get(0)
            .and_then(|obj| obj.get("toBlock"))
            .and_then(|s| s.as_str()).unwrap_or("latest");
        let address = params.get(0).and_then(|obj| obj.get("address"));
        let topics =  params.get(0).and_then(|obj| obj.get("topics"));

        // Parse the address into a vec of strings
        let addresses = match address {
            Some(&Value::String(ref single)) => vec![single.clone()],
            Some(&Value::Array(ref multiple)) => multiple.iter().map(|addr_val| {
                let s = addr_val.as_str().unwrap_or("");
                String::from(s)
            }).collect(),
            Some(&Value::Null) => vec![],
            None => vec![],
            Some(_) => {
                return Err(Error::invalid_params("Invalid value for 'address'"));
            }
        };

        let parsed_topics = match topics {
            Some(value) => Topic::from_value(value),
            None => Topic::Null
        };

        Ok(LogFilterSpec {
            from_block: String::from(from_block),
            to_block: String::from(to_block),
            addresses: addresses,
            topics: parsed_topics
        })
    }
}

#[derive(Debug, Clone)]
pub enum Filter {
    Block,
    Transaction,
    Log(LogFilterSpec)
}

#[cfg(test)]
mod tests {
    use super::Topic;
    use jsonrpc_core::Value;

    #[test]
    fn parse_topics() {
        assert_eq!(Topic::Null, Topic::from_value(&Value::Null));
        assert_eq!(Topic::Data(String::from("foo")),
                   Topic::from_value(&Value::String(String::from("foo"))));
    }
}
