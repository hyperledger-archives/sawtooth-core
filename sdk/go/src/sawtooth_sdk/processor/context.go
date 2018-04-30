/**
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

package processor

import (
	"fmt"
	"github.com/golang/protobuf/proto"
	"sawtooth_sdk/messaging"
	"sawtooth_sdk/protobuf/events_pb2"
	"sawtooth_sdk/protobuf/state_context_pb2"
	"sawtooth_sdk/protobuf/validator_pb2"
)

// Context provides an abstract interface for getting and setting validator
// state. All validator interactions by a handler should be through a Context
// instance. Currently, the Context class is NOT thread-safe and Context classes
// may not share the same messaging.Connection object.
type Context struct {
	connection messaging.Connection
	contextId  string
}

type Attribute struct {
	Key   string
	Value string
}

// Construct a new context object given an initialized Stream and Context ID.
func NewContext(connection messaging.Connection, contextId string) *Context {
	return &Context{
		connection: connection,
		contextId:  contextId,
	}
}

// GetState queries the validator state for data at each of the addresses in the
// given slice. A string->[]byte map is returned. If an address is not set,
// it will not exist in the map.
//
//     results, err := context.Get(addresses)
//     if err != nil {
//         fmt.Println("Error getting data!")
//     }
//     data, ok := results[address]
//     if !ok {
//         fmt.Prinln("No data stored at address!")
//     }
//
func (self *Context) GetState(addresses []string) (map[string][]byte, error) {
	// Construct the message
	request := &state_context_pb2.TpStateGetRequest{
		ContextId: self.contextId,
		Addresses: addresses,
	}
	bytes, err := proto.Marshal(request)
	if err != nil {
		return nil, fmt.Errorf("Failed to marshal TpStateGetRequest: %v", err)
	}

	// Send the message and get the response
	corrId, err := self.connection.SendNewMsg(
		validator_pb2.Message_TP_STATE_GET_REQUEST, bytes,
	)
	if err != nil {
		return nil, fmt.Errorf("Failed to send TpStateGetRequest: %v", err)
	}

	_, msg, err := self.connection.RecvMsgWithId(corrId)
	if msg.GetCorrelationId() != corrId {
		return nil, fmt.Errorf(
			"Expected message with correlation id %v but got %v",
			corrId, msg.GetCorrelationId(),
		)
	}

	if msg.GetMessageType() != validator_pb2.Message_TP_STATE_GET_RESPONSE {
		return nil, fmt.Errorf(
			"Expected TpStateGetResponse but got %v", msg.GetMessageType(),
		)
	}

	// Parse the result
	response := &state_context_pb2.TpStateGetResponse{}
	err = proto.Unmarshal(msg.GetContent(), response)
	if err != nil {
		return nil, fmt.Errorf("Failed to unmarshal TpStateGetResponse: %v", err)
	}

	// Use a switch in case new Status values are added
	switch response.Status {
	case state_context_pb2.TpStateGetResponse_AUTHORIZATION_ERROR:
		return nil, &AuthorizationException{Msg: fmt.Sprint("Tried to get unauthorized address: ", addresses)}
	}

	// Construct and return a map
	results := make(map[string][]byte)
	for _, entry := range response.GetEntries() {
		if len(entry.GetData()) != 0 {
			results[entry.GetAddress()] = entry.GetData()
		}
	}

	return results, nil
}

// SetState requests that each address in the validator state be set to the given
// value. A slice of addresses set is returned or an error if there was a
// problem setting the addresses. For example:
//
//     responses, err := context.Set(dataMap)
//     if err != nil {
//         fmt.Println("Error setting addresses!")
//     }
//     set, ok := results[address]
//     if !ok {
//         fmt.Prinln("Address was not set!")
//     }
//
func (self *Context) SetState(pairs map[string][]byte) ([]string, error) {
	// Construct the message
	entries := make([]*state_context_pb2.TpStateEntry, 0, len(pairs))
	for address, data := range pairs {
		entries = append(entries, &state_context_pb2.TpStateEntry{
			Address: address,
			Data:    data,
		})
	}

	request := &state_context_pb2.TpStateSetRequest{
		ContextId: self.contextId,
		Entries:   entries,
	}
	bytes, err := proto.Marshal(request)
	if err != nil {
		return nil, fmt.Errorf("Failed to marshal: %v", err)
	}

	// Send the message and get the response
	corrId, err := self.connection.SendNewMsg(
		validator_pb2.Message_TP_STATE_SET_REQUEST, bytes,
	)
	if err != nil {
		return nil, fmt.Errorf("Failed to send set: %v", err)
	}

	_, msg, err := self.connection.RecvMsgWithId(corrId)
	if msg.GetCorrelationId() != corrId {
		return nil, fmt.Errorf(
			"Expected message with correlation id %v but got %v",
			corrId, msg.GetCorrelationId(),
		)
	}

	if msg.GetMessageType() != validator_pb2.Message_TP_STATE_SET_RESPONSE {
		return nil, fmt.Errorf(
			"Expected TP_STATE_SET_RESPONSE but got %v", msg.GetMessageType(),
		)
	}

	// Parse the result
	response := &state_context_pb2.TpStateSetResponse{}
	err = proto.Unmarshal(msg.Content, response)
	if err != nil {
		return nil, fmt.Errorf("Failed to unmarshal TpStateSetResponse: %v", err)
	}

	// Use a switch in case new Status values are added
	switch response.GetStatus() {
	case state_context_pb2.TpStateSetResponse_AUTHORIZATION_ERROR:
		addresses := make([]string, 0, len(pairs))
		for a, _ := range pairs {
			addresses = append(addresses, a)
		}
		return nil, &AuthorizationException{Msg: fmt.Sprint("Tried to set unauthorized address: ", addresses)}
	}

	return response.GetAddresses(), nil
}

// DeleteState requests that each address in the validator state be
// deleted from state. A slice of addresses deleted is returned or an
// error if there was a problem deleting the addresses. For example:
//
//     responses, err := context.DeleteState(dataMap)
//     if err != nil {
//         fmt.Println("Error deleting addresses!")
//     }
//     delete, ok := results[address]
//     if !ok {
//         fmt.Prinln("Address was not deleted!")
//     }
//
func (self *Context) DeleteState(addresses []string) ([]string, error) {
	// Construct the message
	request := &state_context_pb2.TpStateDeleteRequest{
		ContextId: self.contextId,
		Addresses: addresses,
	}

	bytes, err := proto.Marshal(request)
	if err != nil {
		return nil, fmt.Errorf("Failed to marshal TpStateDeleteRequest: %v", err)
	}

	// Send the message and get the response
	corrId, err := self.connection.SendNewMsg(
		validator_pb2.Message_TP_STATE_DELETE_REQUEST, bytes,
	)
	if err != nil {
		return nil, fmt.Errorf("Failed to send TpStateDeleteRequest: %v", err)
	}

	_, msg, err := self.connection.RecvMsgWithId(corrId)
	if msg.GetCorrelationId() != corrId {
		return nil, fmt.Errorf(
			"Expected message with correlation id %v but got %v",
			corrId, msg.GetCorrelationId(),
		)
	}

	if msg.GetMessageType() != validator_pb2.Message_TP_STATE_DELETE_RESPONSE {
		return nil, fmt.Errorf(
			"Expected TpStateDeleteResponse but got %v", msg.GetMessageType(),
		)
	}

	// Parse the result
	response := &state_context_pb2.TpStateDeleteResponse{}
	err = proto.Unmarshal(msg.GetContent(), response)
	if err != nil {
		return nil, fmt.Errorf("Failed to unmarshal TpStatedDeleteResponse: %v", err)
	}

	// Use a switch in case new Status values are added
	switch response.Status {
	case state_context_pb2.TpStateDeleteResponse_AUTHORIZATION_ERROR:
		return nil, &AuthorizationException{Msg: fmt.Sprint("Tried to get unauthorized address: ", addresses)}
	}

	return response.GetAddresses(), nil
}

// Add a blob to the execution result for this transaction.
func (self *Context) AddReceiptData(data []byte) error {
	// Append the data to the transaction receipt and set the type
	request := &state_context_pb2.TpReceiptAddDataRequest{
		ContextId: self.contextId,
		Data:      data,
	}
	bytes, err := proto.Marshal(request)
	if err != nil {
		return fmt.Errorf("Failed to marshal: %v", err)
	}

	// Send the message and get the response
	corrId, err := self.connection.SendNewMsg(
		validator_pb2.Message_TP_RECEIPT_ADD_DATA_REQUEST, bytes,
	)
	if err != nil {
		return fmt.Errorf("Failed to add receipt data: %v", err)
	}

	_, msg, err := self.connection.RecvMsgWithId(corrId)
	if msg.GetCorrelationId() != corrId {
		return fmt.Errorf(
			"Expected message with correlation id %v but got %v",
			corrId, msg.GetCorrelationId(),
		)
	}

	if msg.GetMessageType() != validator_pb2.Message_TP_RECEIPT_ADD_DATA_RESPONSE {
		return fmt.Errorf(
			"Expected TP_RECEIPT_ADD_DATA_RESPONSE but got %v", msg.GetMessageType(),
		)
	}

	// Parse the result
	response := &state_context_pb2.TpReceiptAddDataResponse{}
	err = proto.Unmarshal(msg.Content, response)
	if err != nil {
		return fmt.Errorf("Failed to unmarshal TpReceiptAddDataResponse: %v", err)
	}

	// Use a switch in case new Status values are added
	switch response.GetStatus() {
	case state_context_pb2.TpReceiptAddDataResponse_ERROR:
		return fmt.Errorf("Failed to add receipt data")
	}

	return nil
}

// Add a new event to the execution result for this transaction.
func (self *Context) AddEvent(event_type string, attributes []Attribute, event_data []byte) error {
	event_attributes := make([]*events_pb2.Event_Attribute, 0, len(attributes))
	for _, attribute := range attributes {
		event_attributes = append(
			event_attributes,
			&events_pb2.Event_Attribute{
				Key:   attribute.Key,
				Value: attribute.Value,
			},
		)
	}

	event := &events_pb2.Event{
		EventType:  event_type,
		Attributes: event_attributes,
		Data:       event_data,
	}

	// Construct message
	request := &state_context_pb2.TpEventAddRequest{
		ContextId: self.contextId,
		Event:     event,
	}
	bytes, err := proto.Marshal(request)
	if err != nil {
		return fmt.Errorf("Failed to marshal: %v", err)
	}

	// Send the message and get the response
	corrId, err := self.connection.SendNewMsg(
		validator_pb2.Message_TP_EVENT_ADD_REQUEST, bytes,
	)
	if err != nil {
		return fmt.Errorf("Failed to add event: %v", err)
	}

	_, msg, err := self.connection.RecvMsgWithId(corrId)
	if msg.GetCorrelationId() != corrId {
		return fmt.Errorf(
			"Expected message with correlation id %v but got %v",
			corrId, msg.GetCorrelationId(),
		)
	}

	if msg.GetMessageType() != validator_pb2.Message_TP_EVENT_ADD_RESPONSE {
		return fmt.Errorf(
			"Expected TP_EVENT_ADD_RESPONSE but got %v", msg.GetMessageType(),
		)
	}

	// Parse the result
	response := &state_context_pb2.TpEventAddResponse{}
	err = proto.Unmarshal(msg.Content, response)
	if err != nil {
		return fmt.Errorf("Failed to unmarshal TpEventAddResponse: %v", err)
	}

	// Use a switch in case new Status values are added
	switch response.GetStatus() {
	case state_context_pb2.TpEventAddResponse_ERROR:
		return fmt.Errorf("Failed to add event")
	}

	return nil
}
