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

package tests

import (
	"fmt"
	"github.com/golang/mock/gomock"
	"github.com/golang/protobuf/proto"
	"mocks/mock_messaging"
	"sawtooth_sdk/messaging"
	"sawtooth_sdk/processor"
	"sawtooth_sdk/protobuf/events_pb2"
	"sawtooth_sdk/protobuf/state_context_pb2"
	"sawtooth_sdk/protobuf/validator_pb2"
	"testing"
)

func TestState(t *testing.T) {
	mockCtrl := gomock.NewController(t)
	defer mockCtrl.Finish()

	var connection messaging.Connection
	mock_connection := mock_messaging.NewMockConnection(mockCtrl)
	connection = mock_connection
	context := processor.NewContext(connection, "abc")

	request := &state_context_pb2.TpStateGetRequest{
		ContextId: "abc",
		Addresses: []string{"abc"},
	}
	bytes, _ := proto.Marshal(request)

	mock_connection.EXPECT().SendNewMsg(validator_pb2.Message_TP_STATE_GET_REQUEST, bytes)
	mock_connection.EXPECT().RecvMsgWithId("")

	context.GetState([]string{"abc"})
}

func TestAddEvent(t *testing.T) {
	mockCtrl := gomock.NewController(t)
	defer mockCtrl.Finish()

	var connection messaging.Connection
	mock_connection := mock_messaging.NewMockConnection(mockCtrl)
	connection = mock_connection
	context := processor.NewContext(connection, "asdf")

	event_attributes := make([]*events_pb2.Event_Attribute, 0)
	event_attributes = append(
		event_attributes,
		&events_pb2.Event_Attribute{
			Key:   "key",
			Value: "value",
		},
	)

	event := &events_pb2.Event{
		EventType:  "test",
		Attributes: event_attributes,
		Data:       []byte("data"),
	}

	request := &state_context_pb2.TpEventAddRequest{
		ContextId: "asdf",
		Event:     event,
	}
	request_bytes, _ := proto.Marshal(request)

	response_bytes, err := proto.Marshal(&state_context_pb2.TpEventAddResponse{
		Status: state_context_pb2.TpEventAddResponse_OK,
	})

	mock_connection.EXPECT().SendNewMsg(validator_pb2.Message_TP_EVENT_ADD_REQUEST, request_bytes)
	mock_connection.EXPECT().RecvMsgWithId("").
		Return(
			"",
			&validator_pb2.Message{
				MessageType:   validator_pb2.Message_TP_EVENT_ADD_RESPONSE,
				CorrelationId: "",
				Content:       response_bytes,
			},
			err)

	attributes := []processor.Attribute{{"key", "value"}}
	add_event_err := context.AddEvent("test", attributes, []byte("data"))
	if add_event_err != nil {
		t.Error(fmt.Errorf("ERROR: %s", add_event_err))
	}
}

func TestReceiptData(t *testing.T) {
	mockCtrl := gomock.NewController(t)
	defer mockCtrl.Finish()

	var connection messaging.Connection
	mock_connection := mock_messaging.NewMockConnection(mockCtrl)
	connection = mock_connection
	context := processor.NewContext(connection, "qwerty")

	request := &state_context_pb2.TpReceiptAddDataRequest{
		ContextId: "qwerty",
		Data:      []byte("receiptdata"),
	}
	bytes, _ := proto.Marshal(request)

	mock_connection.EXPECT().SendNewMsg(validator_pb2.Message_TP_RECEIPT_ADD_DATA_REQUEST, bytes)
	mock_connection.EXPECT().RecvMsgWithId("")

	context.AddReceiptData([]byte("receiptdata"))
}
