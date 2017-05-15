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
	"sawtooth_sdk/protobuf/state_context_pb2"
	"sawtooth_sdk/protobuf/validator_pb2"
)

// State provides an abstract interface for getting and setting validator
// state. All validator interactions by a handler should be through a State
// instance. Currently, the State class is NOT thread-safe and State classes
// may not share the same messaging.Connection object.
type State struct {
	connection *messaging.Connection
	contextId  string
}

// Construct a new state cobject given an initialized Stream and Context ID.
func NewState(connection *messaging.Connection, contextId string) *State {
	return &State{
		connection: connection,
		contextId:  contextId,
	}
}

// Get queries the validator state for data at each of the addresses in the
// given slice. A string->[]byte map is returned. If an address is not set, the
// slice in the map will have 0 length. For example:
//
//     results, err := state.Get(addresses)
//     if err != nil {
//         fmt.Println("Error getting data!")
//     }
//     data, ok := results[address]
//     if !ok || len(data) == 0 {
//         fmt.Prinln("No data stored at address!")
//     }
//
func (self *State) Get(addresses []string) (map[string][]byte, error) {
	logger.Debugf("Getting %v", addresses)

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
	if err != nil {
		return nil, fmt.Errorf("Failed to received TpStateGetResponse: %v", err)
	}

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
		return nil, fmt.Errorf(
			"Tried to get unauthorized address: %v", addresses,
		)
	}

	// Construct and return a map
	results := make(map[string][]byte)
	for _, entry := range response.GetEntries() {
		results[entry.GetAddress()] = entry.GetData()
	}
	logger.Debugf("Got %v", results)

	return results, nil
}

// Set requests that each address in the validator state be set to the given
// value. A slice of addresses set is returned or an error if there was a
// problem setting the addresses. For example:
//
//     responses, err := state.Set(dataMap)
//     if err != nil {
//         fmt.Println("Error setting addresses!")
//     }
//     set, ok := results[address]
//     if !ok {
//         fmt.Prinln("Address was not set!")
//     }
//
func (self *State) Set(pairs map[string][]byte) ([]string, error) {
	logger.Debugf("Setting %v", pairs)
	// Construct the message
	entries := make([]*state_context_pb2.Entry, 0, len(pairs))
	for address, data := range pairs {
		entries = append(entries, &state_context_pb2.Entry{
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
	if err != nil {
		return nil, fmt.Errorf("Failed to receive TpStateSetResponse: %v", err)
	}
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
		return nil, fmt.Errorf("Tried to set unauthorized address: %v", addresses)
	}

	logger.Debugf("Set %v", response.Addresses)

	return response.Addresses, nil
}
