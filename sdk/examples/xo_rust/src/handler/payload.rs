/*
 * Copyright 2018 Bitwise IO, Inc.
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

use sawtooth_sdk::processor::handler::ApplyError;

pub struct XoPayload {
    name: String,
    action: String,
    space: usize,
}

impl XoPayload {
    // payload_data is a utf-8 encoded string
    pub fn new(payload_data: &[u8]) -> Result<XoPayload, ApplyError> {
        let payload_string = match ::std::str::from_utf8(&payload_data) {
            Ok(s) => s,
            Err(_) => {
                return Err(ApplyError::InvalidTransaction(String::from(
                    "Invalid payload serialization",
                )))
            }
        };

        let items: Vec<&str> = payload_string.split(",").collect();

        if items.len() != 3 {
            return Err(ApplyError::InvalidTransaction(String::from(
                "Payload must have exactly 2 commas",
            )));
        }

        let (name, action, space) = (items[0], items[1], items[2]);

        if name.is_empty() {
            return Err(ApplyError::InvalidTransaction(String::from(
                "Name is required",
            )));
        }

        if action.is_empty() {
            return Err(ApplyError::InvalidTransaction(String::from(
                "Action is required",
            )));
        }

        if name.contains("|") {
            return Err(ApplyError::InvalidTransaction(String::from(
                "Name cannot contain |",
            )));
        }
        match action {
            "create" | "take" | "delete" => (),
            _ => {
                return Err(ApplyError::InvalidTransaction(String::from(
                    format!("Invalid action: {}", action).as_str(),
                )));
            }
        };

        let mut space_parsed: usize = 0; // Default, invalid value
        if action == "take" {
            if space.is_empty() {
                return Err(ApplyError::InvalidTransaction(String::from(
                    "Space is required with action `take`",
                )));
            }
            space_parsed = match space.parse() {
                Ok(num) => num,
                Err(_) => {
                    return Err(ApplyError::InvalidTransaction(String::from(
                        "Space must be an integer",
                    )))
                }
            };
            if space_parsed < 1 || space_parsed > 9 {
                return Err(ApplyError::InvalidTransaction(String::from(
                    "Space must be an integer from 1 to 9",
                )));
            }
        }

        Ok(XoPayload {
            name: name.to_string(),
            action: action.to_string(),
            space: space_parsed,
        })
    }

    pub fn get_name(&self) -> String {
        self.name.clone()
    }

    pub fn get_action(&self) -> String {
        self.action.clone()
    }

    pub fn get_space(&self) -> usize {
        self.space
    }
}
