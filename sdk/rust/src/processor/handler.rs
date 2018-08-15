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

#![allow(unknown_lints)]

extern crate protobuf;
extern crate rand;
extern crate zmq;

use protobuf::Message as M;
use protobuf::RepeatedField;

use std;
use std::borrow::Borrow;
use std::collections::HashMap;
use std::error::Error as StdError;

use messages::events::Event;
use messages::events::Event_Attribute;
use messages::processor::TpProcessRequest;
use messages::state_context::*;
use messages::validator::Message_MessageType;

use messaging::stream::MessageSender;
use messaging::stream::ReceiveError;
use messaging::stream::SendError;
use messaging::zmq_stream::ZmqMessageSender;

use super::generate_correlation_id;

#[derive(Debug)]
pub enum ApplyError {
    /// Returned for an Invalid Transaction.
    InvalidTransaction(String),
    /// Returned when an internal error occurs during transaction processing.
    InternalError(String),
}

impl std::error::Error for ApplyError {
    fn description(&self) -> &str {
        match *self {
            ApplyError::InvalidTransaction(ref msg) => msg,
            ApplyError::InternalError(ref msg) => msg,
        }
    }

    fn cause(&self) -> Option<&std::error::Error> {
        match *self {
            ApplyError::InvalidTransaction(_) => None,
            ApplyError::InternalError(_) => None,
        }
    }
}

impl std::fmt::Display for ApplyError {
    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
        match *self {
            ApplyError::InvalidTransaction(ref s) => write!(f, "InvalidTransaction: {}", s),
            ApplyError::InternalError(ref s) => write!(f, "InternalError: {}", s),
        }
    }
}

#[derive(Debug)]
pub enum ContextError {
    /// Returned for an authorization error
    AuthorizationError(String),
    /// Returned when a error occurs due to missing info in a response
    ResponseAttributeError(String),
    /// Returned when there is an issues setting receipt data or events.
    TransactionReceiptError(String),
    /// Returned when a ProtobufError is returned during serializing
    SerializationError(Box<StdError>),
    /// Returned when an error is returned when sending a message
    SendError(Box<StdError>),
    /// Returned when an error is returned when sending a message
    ReceiveError(Box<StdError>),
}

impl std::error::Error for ContextError {
    fn description(&self) -> &str {
        match *self {
            ContextError::AuthorizationError(ref msg) => msg,
            ContextError::ResponseAttributeError(ref msg) => msg,
            ContextError::TransactionReceiptError(ref msg) => msg,
            ContextError::SerializationError(ref err) => err.description(),
            ContextError::SendError(ref err) => err.description(),
            ContextError::ReceiveError(ref err) => err.description(),
        }
    }

    fn cause(&self) -> Option<&std::error::Error> {
        match *self {
            ContextError::AuthorizationError(_) => None,
            ContextError::ResponseAttributeError(_) => None,
            ContextError::TransactionReceiptError(_) => None,
            ContextError::SerializationError(ref err) => Some(err.borrow()),
            ContextError::SendError(ref err) => Some(err.borrow()),
            ContextError::ReceiveError(ref err) => Some(err.borrow()),
        }
    }
}

impl std::fmt::Display for ContextError {
    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
        match *self {
            ContextError::AuthorizationError(ref s) => write!(f, "AuthorizationError: {}", s),
            ContextError::ResponseAttributeError(ref s) => {
                write!(f, "ResponseAttributeError: {}", s)
            }
            ContextError::TransactionReceiptError(ref s) => {
                write!(f, "TransactionReceiptError: {}", s)
            }
            ContextError::SerializationError(ref err) => {
                write!(f, "SerializationError: {}", err.description())
            }
            ContextError::SendError(ref err) => write!(f, "SendError: {}", err.description()),
            ContextError::ReceiveError(ref err) => write!(f, "ReceiveError: {}", err.description()),
        }
    }
}

impl From<ContextError> for ApplyError {
    fn from(context_error: ContextError) -> Self {
        match context_error {
            ContextError::TransactionReceiptError(..) => {
                ApplyError::InternalError(format!("{}", context_error))
            }
            _ => ApplyError::InvalidTransaction(format!("{}", context_error)),
        }
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

#[derive(Clone)]
pub struct TransactionContext {
    context_id: String,
    sender: ZmqMessageSender,
}

impl TransactionContext {
    /// Context provides an interface for getting, setting, and deleting
    /// validator state. All validator interactions by a handler should be
    /// through a Context instance.
    ///
    /// # Arguments
    ///
    /// * `sender` - for client grpc communication
    /// * `context_id` - the context_id passed in from the validator
    pub fn new(context_id: &str, sender: ZmqMessageSender) -> TransactionContext {
        TransactionContext {
            context_id: String::from(context_id),
            sender,
        }
    }

    /// get_state queries the validator state for data at each of the
    /// addresses in the given list. The addresses that have been set
    /// are returned.
    ///
    /// # Arguments
    ///
    /// * `addresses` - the addresses to fetch
    #[allow(needless_pass_by_value)]
    pub fn get_state(&mut self, addresses: Vec<String>) -> Result<Option<Vec<u8>>, ContextError> {
        let mut request = TpStateGetRequest::new();
        request.set_context_id(self.context_id.clone());
        request.set_addresses(RepeatedField::from_vec(addresses.to_vec()));
        let serialized = request.write_to_bytes()?;
        let x: &[u8] = &serialized;

        let mut future = self.sender.send(
            Message_MessageType::TP_STATE_GET_REQUEST,
            &generate_correlation_id(),
            x,
        )?;

        let response: TpStateGetResponse = protobuf::parse_from_bytes(future.get()?.get_content())?;
        match response.get_status() {
            TpStateGetResponse_Status::OK => {
                let entry = match response.get_entries().first() {
                    Some(x) => x,
                    None => {
                        return Err(ContextError::ResponseAttributeError(String::from(
                            "TpStateGetResponse is missing entries.",
                        )))
                    }
                };
                match entry.get_data().len() {
                    0 => Ok(None),
                    _ => Ok(Some(Vec::from(entry.get_data()))),
                }
            }
            TpStateGetResponse_Status::AUTHORIZATION_ERROR => {
                Err(ContextError::AuthorizationError(format!(
                    "Tried to get unauthorized address: {:?}",
                    addresses
                )))
            }
            TpStateGetResponse_Status::STATUS_UNSET => Err(ContextError::ResponseAttributeError(
                String::from("Status was not set for TpStateGetResponse"),
            )),
        }
    }

    /// set_state requests that each address in the provided map be
    /// set in validator state to its corresponding value.
    ///
    /// # Arguments
    ///
    /// * `address` - address of where to store the data
    /// * `paylaod` - payload is the data to store at the address
    #[allow(needless_pass_by_value)]
    pub fn set_state(&mut self, entries: HashMap<String, Vec<u8>>) -> Result<(), ContextError> {
        let state_entries: Vec<TpStateEntry> = entries
            .iter()
            .map(|(address, payload)| {
                let mut entry = TpStateEntry::new();
                entry.set_address(address.to_string());
                entry.set_data(payload.to_vec());
                entry
            }).collect();

        let mut request = TpStateSetRequest::new();
        request.set_context_id(self.context_id.clone());
        request.set_entries(RepeatedField::from_vec(state_entries.to_vec()));
        let serialized = request.write_to_bytes()?;
        let x: &[u8] = &serialized;

        let mut future = self.sender.send(
            Message_MessageType::TP_STATE_SET_REQUEST,
            &generate_correlation_id(),
            x,
        )?;

        let response: TpStateSetResponse = protobuf::parse_from_bytes(future.get()?.get_content())?;
        match response.get_status() {
            TpStateSetResponse_Status::OK => Ok(()),
            TpStateSetResponse_Status::AUTHORIZATION_ERROR => {
                Err(ContextError::AuthorizationError(format!(
                    "Tried to set unauthorized address: {:?}",
                    state_entries
                )))
            }
            TpStateSetResponse_Status::STATUS_UNSET => Err(ContextError::ResponseAttributeError(
                String::from("Status was not set for TpStateSetResponse"),
            )),
        }
    }

    /// delete_state requests that each of the provided addresses be unset
    /// in validator state. A list of successfully deleted addresses
    ///  is returned.
    ///
    /// # Arguments
    ///
    /// * `addresses` - the addresses to fetch
    #[allow(needless_pass_by_value)]
    pub fn delete_state(
        &mut self,
        addresses: Vec<String>,
    ) -> Result<Option<Vec<String>>, ContextError> {
        let mut request = TpStateDeleteRequest::new();
        request.set_context_id(self.context_id.clone());
        request.set_addresses(RepeatedField::from_vec(addresses.clone()));

        let serialized = request.write_to_bytes()?;
        let x: &[u8] = &serialized;

        let mut future = self.sender.send(
            Message_MessageType::TP_STATE_DELETE_REQUEST,
            &generate_correlation_id(),
            x,
        )?;

        let response: TpStateDeleteResponse =
            protobuf::parse_from_bytes(future.get()?.get_content())?;
        match response.get_status() {
            TpStateDeleteResponse_Status::OK => Ok(Some(Vec::from(response.get_addresses()))),
            TpStateDeleteResponse_Status::AUTHORIZATION_ERROR => {
                Err(ContextError::AuthorizationError(format!(
                    "Tried to delete unauthorized address: {:?}",
                    addresses
                )))
            }
            TpStateDeleteResponse_Status::STATUS_UNSET => {
                Err(ContextError::ResponseAttributeError(String::from(
                    "Status was not set for TpStateDeleteResponse",
                )))
            }
        }
    }

    /// add_receipt_data adds a blob to the execution result for this transaction
    ///
    /// # Arguments
    ///
    /// * `data` - the data to add
    pub fn add_receipt_data(&mut self, data: &[u8]) -> Result<(), ContextError> {
        let mut request = TpReceiptAddDataRequest::new();
        request.set_context_id(self.context_id.clone());
        request.set_data(Vec::from(data));

        let serialized = request.write_to_bytes()?;
        let x: &[u8] = &serialized;

        let mut future = self.sender.send(
            Message_MessageType::TP_RECEIPT_ADD_DATA_REQUEST,
            &generate_correlation_id(),
            x,
        )?;

        let response: TpReceiptAddDataResponse =
            protobuf::parse_from_bytes(future.get()?.get_content())?;
        match response.get_status() {
            TpReceiptAddDataResponse_Status::OK => Ok(()),
            TpReceiptAddDataResponse_Status::ERROR => Err(ContextError::TransactionReceiptError(
                format!("Failed to add receipt data {:?}", data),
            )),
            TpReceiptAddDataResponse_Status::STATUS_UNSET => {
                Err(ContextError::ResponseAttributeError(String::from(
                    "Status was not set for TpReceiptAddDataResponse",
                )))
            }
        }
    }

    /// add_event adds a new event to the execution result for this transaction.
    ///
    /// # Arguments
    ///
    /// * `event_type` -  This is used to subscribe to events. It should be globally unique and
    ///         describe what, in general, has occured.
    /// * `attributes` - Additional information about the event that is transparent to the
    ///          validator. Attributes can be used by subscribers to filter the type of events
    ///          they receive.
    /// * `data` - Additional information about the event that is opaque to the validator.
    pub fn add_event(
        &mut self,
        event_type: String,
        attributes: Vec<(String, String)>,
        data: &[u8],
    ) -> Result<(), ContextError> {
        let mut event = Event::new();
        event.set_event_type(event_type);

        let mut attributes_vec = Vec::new();
        for (key, value) in attributes {
            let mut attribute = Event_Attribute::new();
            attribute.set_key(key);
            attribute.set_value(value);
            attributes_vec.push(attribute);
        }
        event.set_attributes(RepeatedField::from_vec(attributes_vec));
        event.set_data(Vec::from(data));

        let mut request = TpEventAddRequest::new();
        request.set_context_id(self.context_id.clone());
        request.set_event(event.clone());

        let serialized = request.write_to_bytes()?;
        let x: &[u8] = &serialized;

        let mut future = self.sender.send(
            Message_MessageType::TP_EVENT_ADD_REQUEST,
            &generate_correlation_id(),
            x,
        )?;

        let response: TpEventAddResponse = protobuf::parse_from_bytes(future.get()?.get_content())?;
        match response.get_status() {
            TpEventAddResponse_Status::OK => Ok(()),
            TpEventAddResponse_Status::ERROR => Err(ContextError::TransactionReceiptError(
                format!("Failed to add event {:?}", event),
            )),
            TpEventAddResponse_Status::STATUS_UNSET => Err(ContextError::ResponseAttributeError(
                String::from("Status was not set for TpEventAddRespons"),
            )),
        }
    }
}

pub trait TransactionHandler {
    /// TransactionHandler that defines the business logic for a new transaction family.
    /// The family_name, family_versions, and namespaces functions are
    /// used by the processor to route processing requests to the handler.

    /// family_name should return the name of the transaction family that this
    /// handler can process, e.g. "intkey"
    fn family_name(&self) -> String;

    /// family_versions should return a list of versions this transaction
    /// family handler can process, e.g. ["1.0"]
    fn family_versions(&self) -> Vec<String>;

    /// namespaces should return a list containing all the handler's
    /// namespaces, e.g. ["abcdef"]
    fn namespaces(&self) -> Vec<String>;

    /// Apply is the single method where all the business logic for a
    /// transaction family is defined. The method will be called by the
    /// transaction processor upon receiving a TpProcessRequest that the
    /// handler understands and will pass in the TpProcessRequest and an
    /// initialized instance of the Context type.
    fn apply(
        &self,
        request: &TpProcessRequest,
        context: &mut TransactionContext,
    ) -> Result<(), ApplyError>;
}
