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
    "testing"
    "github.com/golang/protobuf/proto"
    "sawtooth_sdk/processor"
    "sawtooth_sdk/messaging"
    "mocks/mock_messaging"
    "sawtooth_sdk/protobuf/validator_pb2"
    "sawtooth_sdk/protobuf/state_context_pb2"
    "github.com/golang/mock/gomock"
)

func TestState(t *testing.T) {
  mockCtrl := gomock.NewController(t)
  defer mockCtrl.Finish()

  var connection messaging.Connection
  mock_connection := mock_messaging.NewMockConnection(mockCtrl)
  connection = mock_connection
  state := processor.NewState(connection, "abc")

  request := &state_context_pb2.TpStateGetRequest{
		ContextId: "abc",
		Addresses: []string{"abc"},
	}
	bytes, _ := proto.Marshal(request)

  mock_connection.EXPECT().SendNewMsg(validator_pb2.Message_TP_STATE_GET_REQUEST, bytes)
  mock_connection.EXPECT().RecvMsgWithId("")

  state.Get([]string{"abc"})
}
