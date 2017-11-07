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
	if err != nil {
		logger.Errorf("Failed to connect to main thread: %v", err)
		return
	}
	defer connection.Close()
	id := connection.Identity()

	// Receive work off of the queue until the queue is closed
	for msg := range queue {
		request := &processor_pb2.TpProcessRequest{}
		err = proto.Unmarshal(msg.GetContent(), request)
		if err != nil {
			logger.Errorf(
				"(%v) Failed to unmarshal TpProcessRequest: %v", id, err,
			)
			break
		}

		header := request.GetHeader()

		// Try to find a handler
		handler, err := findHandler(handlers, header)
		if err != nil {
			logger.Errorf("(%v) Failed to find handler: %v", id, err)
			break
		}

		// Construct a new Context instance for the handler
		contextId := request.GetContextId()
		context := NewContext(connection, contextId)

		// Run the handler
		err = handler.Apply(request, context)

		// Process the handler response
		response := &processor_pb2.TpProcessResponse{}
		if err != nil {
			switch e := err.(type) {
			case *InvalidTransactionError:
				logger.Warnf("(%v) %v", id, e)
				response.Status = processor_pb2.TpProcessResponse_INVALID_TRANSACTION
				response.Message = e.Msg
				response.ExtendedData = e.ExtendedData
			case *InternalError:
				logger.Warnf("(%v) %v", id, e)
				response.Status = processor_pb2.TpProcessResponse_INTERNAL_ERROR
				response.Message = e.Msg
				response.ExtendedData = e.ExtendedData
			case *AuthorizationException:
				logger.Warnf("(%v) %v", id, e)
				response.Status = processor_pb2.TpProcessResponse_INVALID_TRANSACTION
				response.Message = e.Msg
				response.ExtendedData = e.ExtendedData
			default:
				logger.Errorf("(%v) Unknown error: %v", id, err)
				response.Status = processor_pb2.TpProcessResponse_INTERNAL_ERROR
				response.Message = e.Error()
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
			responseData, msg.GetCorrelationId(),
		)
		if err != nil {
			logger.Errorf("(%v) Error sending TpProcessResponse: %v", id, err)
			break
		}
	}

	// Queue has closed, so send shutdown signal
	logger.Infof("(%v) No more work in queue, shutting down", id)
	err = connection.SendMsg(
		validator_pb2.Message_DEFAULT,
		[]byte{byte(0)}, "shutdown",
	)
	if err != nil {
		logger.Errorf("(%v) Error sending shutdown: %v", id, err)
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

		return handler, nil
	}
	return nil, fmt.Errorf(
		"Unknown handler: (%v, %v)", header.GetFamilyName(),
		header.GetFamilyVersion(),
	)
}

// Waits for something to come along a channel and then initiates processor shutdown
func shutdown(context *zmq.Context, uri string, queue chan *validator_pb2.Message, wait chan int) {
	// Wait for a request to shutdown
	connection, err := messaging.NewConnection(context, zmq.DEALER, uri)
	if err != nil {
		logger.Errorf("Failed to connect to main thread: %v", err)
		return
	}
	defer connection.Close()
	id := "shutdown"

	<-wait

	// Send a request to be unregistered
	data, err := proto.Marshal(&processor_pb2.TpUnregisterRequest{})
	if err != nil {
		logger.Errorf(
			"Failed to unregister: %v", err,
		)
	}
	corrId, err := connection.SendNewMsg(
		validator_pb2.Message_TP_UNREGISTER_REQUEST, data,
	)
	if err != nil {
		logger.Errorf(
			"Failed to unregister: %v", err,
		)
	}

	// Wait for a response
	_, msg, err := connection.RecvMsgWithId(corrId)
	if err != nil {
		logger.Errorf("Failed to receive TpUnregisterResponse: %v", err)
	}
	if msg.GetCorrelationId() != corrId {
		logger.Errorf(
			"Expected message with correlation id %v but got %v",
			corrId, msg.GetCorrelationId(),
		)
	}
	if msg.GetMessageType() != validator_pb2.Message_TP_UNREGISTER_RESPONSE {
		logger.Errorf(
			"Expected TP_UNREGISTER_RESPONSE but got %v", msg.GetMessageType(),
		)
	}

	// Close the work queue, telling the worker threads there's no more work
	close(queue)

	err = connection.SendMsg(
		validator_pb2.Message_DEFAULT,
		[]byte{byte(0)}, "shutdown",
	)
	if err != nil {
		logger.Errorf("(%v) Error sending shutdown message to router: %v", id, err)
	} else {
		logger.Infof("(%v) Sent shutdown message to router", id)
	}
}
