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
	zmq "github.com/pebbe/zmq4"
	"sawtooth_sdk/messaging"
	"sawtooth_sdk/protobuf/processor_pb2"
	"sawtooth_sdk/protobuf/transaction_pb2"
	"sawtooth_sdk/protobuf/validator_pb2"
)

// The main worker thread finds an appropriate handler and processes the request
func worker(context *zmq.Context, uri string, queue chan *validator_pb2.Message, handlers []TransactionHandler) {
	// Connect to the main send/receive thread
	connection, err := messaging.NewConnection(context, zmq.DEALER, uri)
	id := connection.Identity()
	if err != nil {
		logger.Errorf("(%v) Failed to connect to main thread: %v", id, err)
		return
	}
	defer connection.Close()

	for {
		// Receive some work off of the queue
		msg := <-queue
		logger.Infof("(%v) Received %v", id, msg.MessageType)

		// Validate the message
		if msg.MessageType != validator_pb2.Message_TP_PROCESS_REQUEST {
			logger.Errorf("(%v) received unexpected message: %v", id, msg)
			break
		}

		request := &processor_pb2.TpProcessRequest{}
		err = proto.Unmarshal(msg.Content, request)
		if err != nil {
			logger.Errorf(
				"(%v) Failed to unmarshal TpProcessRequest: %v", id, err,
			)
			break
		}

		header := &transaction_pb2.TransactionHeader{}
		err = proto.Unmarshal(request.Header, header)
		if err != nil {
			logger.Errorf(
				"(%v) Failed to unmarshal TransactionHeader: %v", id, err)
			break
		}

		// Try to find a handler
		handler, err := findHandler(handlers, header)
		if err != nil {
			logger.Errorf("(%v) Failed to find handler: %v", id, err)
			break
		}

		// Construct a new State instance for the handler
		contextId := request.GetContextId()
		state := NewState(connection, contextId)

		// Run the handler
		logger.Debugf(
			"(%v) Passing request with context id %v to handler (%v, %v, %v, %v)",
			id, contextId, handler.FamilyName(), handler.FamilyVersion,
			handler.Encoding(), handler.Namespaces(),
		)
		err = handler.Apply(request, state)

		// Process the handler response
		response := &processor_pb2.TpProcessResponse{}
		if err != nil {
			switch e := err.(type) {
			case *InvalidTransactionError:
				logger.Warnf("(%v) Invalid Transaction: %v", id, e)
				response.Status = processor_pb2.TpProcessResponse_INVALID_TRANSACTION
			case *InternalError:
				logger.Warnf("(%v) Internal Error %v", id, e)
				response.Status = processor_pb2.TpProcessResponse_INTERNAL_ERROR
			default:
				logger.Errorf("(%v) Unknown error: %v", id, err)
				response.Status = processor_pb2.TpProcessResponse_INTERNAL_ERROR
			}
		} else {
			response.Status = processor_pb2.TpProcessResponse_OK
		}

		responseData, err := proto.Marshal(response)
		if err != nil {
			logger.Errorf("(%v) Failed to marshal TpProcessResponse: %v", id, err)
			break
		}

		// Send back a response to the validator
		err = connection.SendMsg(
			validator_pb2.Message_TP_PROCESS_RESPONSE,
			responseData, msg.CorrelationId,
		)
		if err != nil {
			logger.Errorf("(%v) Error sending TpProcessResponse: %v", id, err)
			break
		}
		logger.Infof("(%v) Responded with %v", id, response.Status)
	}
}

// Searches for and returns a handler that matches the header. If a suitable
// handler is not found, returns an error.
func findHandler(handlers []TransactionHandler, header *transaction_pb2.TransactionHeader) (TransactionHandler, error) {
	for _, handler := range handlers {
		if header.GetFamilyName() != handler.FamilyName() {
			break
		}

		if header.GetFamilyVersion() != handler.FamilyVersion() {
			break
		}

		if header.GetPayloadEncoding() != handler.Encoding() {
			break
		}

		return handler, nil
	}
	return nil, fmt.Errorf(
		"Unknown handler: (%v, %v, %v)", header.GetFamilyName(),
		header.GetFamilyVersion(), header.GetPayloadEncoding(),
	)
}
