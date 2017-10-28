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

extern crate zmq;
extern crate protobuf;
extern crate rand;

use protobuf::Message as M;
use protobuf::RepeatedField;

use self::rand::Rng;

use std::error::Error as StdError;
use std;
use std::borrow::Borrow;

use messages::processor::TpProcessRequest;
use messages::state_context::TpStateEntry;
use messages::state_context::TpStateGetRequest;
use messages::state_context::TpStateGetResponse;
use messages::state_context::TpStateGetResponse_Status;
use messages::state_context::TpStateSetRequest;
use messages::state_context::TpStateSetResponse;
use messages::state_context::TpStateSetResponse_Status;
use messages::validator::Message_MessageType;

use messaging::stream::MessageSender;
use messaging::stream::SendError;
use messaging::stream::ReceiveError;
use messaging::zmq_stream::ZmqMessageSender;

#[derive(Debug)]
pub enum ApplyError {
    InvalidTransaction(String),
    InternalError(String)
}

impl std::error::Error for ApplyError {
    fn description(&self) -> &str {
        match *self {
            ApplyError::InvalidTransaction(ref msg) => msg,
            ApplyError::InternalError(ref msg) => msg
        }
    }

    fn cause(&self) -> Option<&std::error::Error> {
        match *self {
            ApplyError::InvalidTransaction(_) => None,
            ApplyError::InternalError(_) => None
        }
    }
}

impl std::fmt::Display for ApplyError {
    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
        match *self {
            ApplyError::InvalidTransaction(ref s) =>
                write!(f, "InvalidTransaction: {}", s),
            ApplyError::InternalError(ref s) =>
                write!(f, "InternalError: {}", s)
        }
    }
}

#[derive(Debug)]
pub enum ContextError {
    /// Raised for an authorization error
    AuthorizationError(String),
    /// Raised when an Unknown error occurs
    UnknownError(String),
    /// Raised for a ProtobufError is returned when serialized.
    SerializationError(Box<StdError>),
    /// Raise when an error is return when sending a message
    SendError(Box<StdError>),
    /// Raise when an error is return when sending a message
    ReceiveError(Box<StdError>),
}

impl std::error::Error for ContextError {
    fn description(&self) -> &str {
        match *self {
            ContextError::AuthorizationError(ref msg) => msg,
            ContextError::UnknownError(ref msg) => msg,
            ContextError::SerializationError(ref err) => err.description(),
            ContextError::SendError(ref err) => err.description(),
            ContextError::ReceiveError(ref err) => err.description(),
        }
    }

    fn cause(&self) -> Option<&std::error::Error> {
        match *self {
            ContextError::AuthorizationError(_) => None,
            ContextError::UnknownError(_) => None,
            ContextError::SerializationError(ref err) => Some(err.borrow()),
            ContextError::SendError(ref err) => Some(err.borrow()),
            ContextError::ReceiveError(ref err) => Some(err.borrow()),
        }
    }
}

impl std::fmt::Display for ContextError {
    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
        match *self {
            ContextError::AuthorizationError(ref s) =>
                write!(f, "AuthorizationError: {}", s),
            ContextError::UnknownError(ref s) =>
                write!(f, "UnknownError: {}", s),
            ContextError::SerializationError(ref err) =>
                write!(f, "SerializationError: {}", err.description()),
            ContextError::SendError(ref err) =>
                write!(f, "SendError: {}", err.description()),
            ContextError::ReceiveError(ref err) =>
                write!(f, "ReceiveError: {}", err.description()),
        }
    }
}

impl From<ContextError> for ApplyError {
    fn from(context_error: ContextError) -> Self {
        ApplyError::InvalidTransaction(format!("{}", context_error))
    }
}

impl From<protobuf::ProtobufError> for ContextError {
    fn from(e: protobuf::ProtobufError) -> Self {
        ContextError::SerializationError(Box::new(e))
    }
}

impl From<SendError> for ContextError {
    fn from(e: SendError) -> Self {
        ContextError::SendError(Box::new(e))
    }
}

impl From<ReceiveError> for ContextError {
    fn from(e: ReceiveError) -> Self {
        ContextError::ReceiveError(Box::new(e))
    }
}

pub struct TransactionContext {
    context_id: String,
    sender: ZmqMessageSender
}

impl TransactionContext {
    pub fn new(context_id: &str, sender: ZmqMessageSender) -> TransactionContext {
        TransactionContext{
            context_id: String::from(context_id),
            sender: sender
        }
    }

    pub fn get_state(&mut self, address: &str) -> Result<Option<Vec<u8>>, ContextError> {
        let mut request = TpStateGetRequest::new();
        request.set_context_id(self.context_id.clone());
        request.set_addresses(RepeatedField::from_vec(vec!(String::from(address))));
        let serialized = request.write_to_bytes()?;
        let x : &[u8] = &serialized;

        let correlation_id: String = rand::thread_rng().gen_ascii_chars().take(16).collect();
        let mut future = self.sender.send(
            Message_MessageType::TP_STATE_GET_REQUEST,
            &correlation_id,
            x)?;

        let response: TpStateGetResponse = protobuf::parse_from_bytes(future.get()?.get_content())?;
        match response.get_status() {
            TpStateGetResponse_Status::OK => {
                let entry = match response.get_entries().first(){
                    Some(x) => x,
                    None => return Err(ContextError::UnknownError(String::from("TpStateGetResponse is missing entries.")))
                };
                match entry.get_data().len() {
                    0 => Ok(None),
                    _ => Ok(Some(Vec::from(match response.get_entries().first() {
                        Some(x) => x.get_data(),
                        None => return Err(ContextError::UnknownError(String::from("No data returned from entry.")))
                    })))
                }
            },
            TpStateGetResponse_Status::AUTHORIZATION_ERROR => {
                Err(ContextError::AuthorizationError(format!("Tried to get unauthorized address: {}", address)))
            },
            TpStateGetResponse_Status::STATUS_UNSET => {
                Err(ContextError::UnknownError(String::from("Status was not set for TpStateGetResponse")))
            }
        }
    }

    pub fn set_state(&mut self, address: &str, payload: &[u8]) -> Result<(), ContextError> {
        let mut entry = TpStateEntry::new();
        entry.set_address(String::from(address));
        entry.set_data(Vec::from(payload));

        let mut request = TpStateSetRequest::new();
        request.set_context_id(self.context_id.clone());
        request.set_entries(RepeatedField::from_slice(&[entry]));
        let serialized = request.write_to_bytes()?;
        let x : &[u8] = &serialized;

        let correlation_id: String = rand::thread_rng().gen_ascii_chars().take(16).collect();
        let mut future = self.sender.send(
            Message_MessageType::TP_STATE_SET_REQUEST,
            &correlation_id,
            x)?;

        let response: TpStateSetResponse = protobuf::parse_from_bytes(future.get()?.get_content())?;
        match response.get_status() {
            TpStateSetResponse_Status::OK => {
                Ok(())
            },
            TpStateSetResponse_Status::AUTHORIZATION_ERROR => {
                Err(ContextError::AuthorizationError(format!("Tried to set unauthorized address: {}", address)))
            },
            TpStateSetResponse_Status::STATUS_UNSET => {
                Err(ContextError::UnknownError(String::from("Status was not set for TpStateSetResponse")))
            }
        }
    }
}

pub trait TransactionHandler {
    fn family_name(&self) -> String;
    fn family_versions(&self) -> Vec<String>;
    fn namespaces(&self) -> Vec<String>;
    fn apply(&self, request: &TpProcessRequest, context: &mut TransactionContext) -> Result<(), ApplyError>;
}
