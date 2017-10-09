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

use std::collections::HashMap;
use std::collections::hash_map::Entry;
use std::sync::{Arc, Mutex};
use client::{Error};
use jsonrpc_core::{Value, Error as RpcError};
use serde_json::Map;

use transform;
use transactions::{SethLog};

// -- Topics --
// A topic filter applies to only one of the four topic entries.
#[derive(Debug, PartialEq, Clone)]
pub enum TopicFilter {
    All, // Match any entry
    Exactly(String), // Match only this entry
    OneOf(Vec<String>), // Match any of the entries in this list
}

impl TopicFilter {
    pub fn from_value(value: &Value) -> Result<Self, RpcError> {
        match value {
            &Value::Array(ref array) => {
                let blobs = array.iter()
                    .map(transform::string_from_hex_value)
                    .collect::<Result<Vec<String>, RpcError>>()?;
                Ok(TopicFilter::OneOf(blobs))
            },
            &Value::String(_) => {
                let blob = transform::string_from_hex_value(value)?;
                Ok(TopicFilter::Exactly(blob))
            },
            &Value::Null => Ok(TopicFilter::All),
            _ => {
                return Err(RpcError::invalid_params("Invalid topic setting"));
            }
        }
    }
    /// The topic passes this filter if:
    ///   1. The filter is All (which corresponds to a null entry in the topic filter list)
    ///   2. The filter is Exactly and the topic and the filter are identitical
    ///   3. The filter is OneOf and the topic is with the filter's list of topics
    pub fn contains(&self, topic: &str) -> bool {
        match self {
            &TopicFilter::All => true,
            &TopicFilter::Exactly(ref blob) => blob == topic,
            &TopicFilter::OneOf(ref blobs) => blobs.contains(&String::from(topic)),
        }
    }
}

// -- LogFilter --
#[derive(Debug, Clone)]
pub struct LogFilter {
    pub from_block: Option<u64>,
    pub to_block: Option<u64>,
    pub addresses: Vec<String>,
    pub topics: Vec<TopicFilter>,
}

impl LogFilter {
    pub fn from_map(filter: Map<String, Value>) -> Result<Self, RpcError> {
        let from_block = match filter.get("fromBlock") {
            Some(s) => {
                let s = transform::u64_from_hex_value(s)?;
                Ok(Some(s))
            },
            None => Ok(None),
        }?;
        let to_block = match filter.get("toBlock") {
            Some(s) => {
                let s = transform::u64_from_hex_value(s)?;
                Ok(Some(s))
            },
            None => Ok(None),
        }?;

        // Parse the address into a vec of strings
        let addresses = match filter.get("address") {
            Some(&Value::Array(ref multiple)) => {
                let addresses = multiple.iter()
                    .map(|addr_val| transform::string_from_hex_value(addr_val))
                    .collect::<Result<Vec<String>, RpcError>>()?;
                addresses
            },
            Some(value) => {
                let address = transform::string_from_hex_value(value)?;
                vec![address]
            },
            None => vec![],
        };

        let topics = transform::get_array_from_map(&filter, "topics").and_then(|topics|
            topics.iter()
                .map(|t| TopicFilter::from_value(t))
                .collect::<Result<Vec<TopicFilter>, RpcError>>())?;

        Ok(LogFilter {
            from_block: from_block,
            to_block: to_block,
            addresses: addresses,
            topics: topics,
        })
    }

    /// The log passes this filter if:
    ///   1. the log's address is in the list of the filter's addresses
    ///   2. the log's topic list is less than or equal to the filter's list of topic filters
    ///   3. the log topic at each index passes the topic filter at that index
    pub fn contains(&self, log: &SethLog, block_num: Option<u64>) -> bool {
        let contains_address = self.contains_address(&log.address);
        let contains_topics = self.contains_topics(&log.topics);
        let contains_block = match block_num {
            Some(block_num) => self.contains_block(block_num),
            None => true,
        };
        contains_address && contains_topics && contains_block
    }

    pub fn contains_address(&self, address: &str) -> bool {
        self.addresses.contains(&String::from(address))
    }

    pub fn contains_topics(&self, topics: &[String]) -> bool {
        self.topics.iter()
            .enumerate()
            .all(|(i, filter)| {
                if let Some(topic) = topics.get(i) {
                    filter.contains(topic)
                } else {
                    false
                }
            })
    }

    pub fn contains_block(&self, block_num: u64) -> bool {
        let lower = match self.from_block {

            Some(n) => block_num >= n,
            None => true,
        };
        let upper = match self.to_block {
            Some(n) => block_num <= n,
            None => true,
        };
        upper && lower
    }
}

pub type FilterId = usize;
pub fn filter_id_from_hex(s: &str) -> Result<FilterId, Error> {
    usize::from_str_radix(s, 16).map_err(|error|
        Error::ParseError(format!("Invalid hex: {}", error)))
}
pub fn filter_id_to_hex(f: FilterId) -> String {
    format!("{:x}", f)
}


#[derive(Debug, Clone)]
pub struct FilterEntry {
    pub filter: Filter,
    pub last_block_sent: u64,
}

#[derive(Debug, Clone)]
pub struct FilterManager {
    id_ctr: Arc<Mutex<FilterId>>,
    filters: Arc<Mutex<HashMap<FilterId, FilterEntry>>>,
}

impl FilterManager {
    pub fn new() -> Self {
        FilterManager{
            id_ctr: Arc::new(Mutex::new(1)),
            filters: Arc::new(Mutex::new(HashMap::new())),
        }
    }

    pub fn new_filter(&mut self, filter: Filter, block_num: u64) -> FilterId {
        let filter_id = {
            let mut ctr = self.id_ctr.lock().unwrap();
            let r = *ctr;
            *ctr += 1;
            r
        };
        self.set_filter(&filter_id, filter, block_num);
        filter_id
    }

    pub fn remove_filter(&mut self, filter_id: &FilterId) -> Option<FilterEntry> {
        self.filters.lock().unwrap().remove(filter_id)
    }

    pub fn get_filter(&mut self, filter_id: &FilterId) -> Option<FilterEntry> {
        self.filters.lock().unwrap().get(filter_id).map(|filter| filter.clone())
    }

    pub fn update_latest_block(&mut self, filter_id: &FilterId, block_num: u64) -> bool {
        if let Entry::Occupied(mut entry) = self.filters.lock().unwrap().entry(*filter_id) {
            (*entry.get_mut()).last_block_sent = block_num;
            true
        } else {
            false
        }
    }

    pub fn set_filter(&mut self, filter_id: &FilterId, filter: Filter, block_num: u64)
        -> Option<FilterEntry>
    {
        let filter_entry = FilterEntry{
            filter: filter,
            last_block_sent: block_num,
        };
        self.filters.lock().unwrap().insert(*filter_id, filter_entry)
    }
}

#[derive(Debug, Clone)]
pub enum Filter {
    Block,
    Transaction,
    Log(LogFilter)
}

#[cfg(test)]
mod tests {
    use super::TopicFilter;
    use jsonrpc_core::Value;

    #[test]
    fn parse_topics() {
        assert_eq!(TopicFilter::Null, TopicFilter::from_value(&Value::Null));
        assert_eq!(TopicFilter::Data(String::from("foo")),
                   TopicFilter::from_value(&Value::String(String::from("foo"))));
    }
}
