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
	"runtime"
	"sawtooth_sdk/logging"
	"sawtooth_sdk/messaging"
	"sawtooth_sdk/protobuf/processor_pb2"
	"sawtooth_sdk/protobuf/transaction_pb2"
	"sawtooth_sdk/protobuf/validator_pb2"
)

var logger *logging.Logger = logging.Get()

// TransactionProcessor is a generic class for communicating with a validator
// and routing transaction processing requests to a registered handler. It uses
// ZMQ and channels to handle requests concurrently.
type TransactionProcessor struct {
	uri      string
	context  *zmq.Context
	ids      map[string]string
	handlers []TransactionHandler
	nThreads int
}

// NewTransactionProcessor initializes a new Transaction Process and points it
// at the given URI. If it fails to initialize, it will panic.
func NewTransactionProcessor(uri string) *TransactionProcessor {
	context, err := zmq.NewContext()
	if err != nil {
		panic(fmt.Sprint("Failed to create ZMQ context: ", err))
	}
	return &TransactionProcessor{
		uri:      uri,
		context:  context,
		ids:      make(map[string]string),
		handlers: make([]TransactionHandler, 0),
		nThreads: runtime.GOMAXPROCS(0),
	}
}

// AddHandler adds the given handler to the TransactionProcessor so it can
// receive transaction processing requests. All handlers must be added prior
// to starting the processor.
func (self *TransactionProcessor) AddHandler(handler TransactionHandler) {
	self.handlers = append(self.handlers, handler)
}

// Set the number of worker threads to be created for handling requests. Must
// be set before calling Start()
func (self *TransactionProcessor) SetThreadCount(n int) {
	self.nThreads = n
}

// Start connects the TransactionProcessor to a validator and starts listening
// for requests and routing them to an appropriate handler.
func (self *TransactionProcessor) Start() error {
	// Establish a connection to the validator
	validator, err := messaging.NewConnection(self.context, zmq.DEALER, self.uri)
	if err != nil {
		return fmt.Errorf("Could not connect to validator: %v", err)
	}
	defer validator.Close()

	// Register all handlers with the validator
	for _, h := range self.handlers {
		err := register(validator, h)
		if err != nil {
			return fmt.Errorf(
				"Error registering handler (%v, %v, %v, %v): %v",
				h.FamilyName(), h.FamilyVersion, h.Encoding(),
				h.Namespaces(), err,
			)
		}
	}

	// Setup connection to internal worker thread pool
	workers, err := messaging.NewConnection(self.context, zmq.ROUTER, "inproc://workers")
	if err != nil {
		return fmt.Errorf("Could not create thread pool router: %v", err)
	}

	queue := make(chan *validator_pb2.Message)
	// Keep track of which correlation ids go to which worker threads, i.e. map
	// corrId->workerThreadId
	ids := make(map[string]string)

	// Startup worker thread pool
	for i := 0; i < self.nThreads; i++ {
		go worker(self.context, "inproc://workers", queue, self.handlers)
	}

	// Setup ZMQ poller for routing messages between worker threads and validator
	poller := zmq.NewPoller()
	poller.Add(validator.Socket(), zmq.POLLIN)
	poller.Add(workers.Socket(), zmq.POLLIN)

	// Poll for messages from worker threads or validator
	for {
		logger.Debugf("Polling...")
		polled, err := poller.Poll(-1)
		if err != nil {
			return fmt.Errorf("Polling failed: %v", err)
		}
		for _, ready := range polled {
			switch socket := ready.Socket; socket {
			case validator.Socket():
				logger.Debugf("Validator has messages waiting")
				receiveValidator(ids, validator, workers, queue)

			case workers.Socket():
				logger.Debugf("Workers have messages waiting")
				receiveWorkers(ids, validator, workers)
			}
		}
	}
}

// Handle incoming messages from the validator
func receiveValidator(ids map[string]string, validator, workers *messaging.Connection, queue chan *validator_pb2.Message) {
	defer func() {
		if r := recover(); r != nil {
			logger.Errorf(
				"Panic occured while routing message from validator: %v", r,
			)
		}
	}()

	// Receive a message from the validator
	_, data, err := validator.RecvData()
	if err != nil {
		logger.Errorf("Receiving message from validator failed: %v", err)
		return
	}
	// We need to deserialize the message to get the correlation id
	msg, err := messaging.LoadMsg(data)
	if err != nil {
		logger.Errorf("Deserializing message from validator failed: %v", err)
		return
	}

	// Check if this is a new request or a response to a message sent by a
	// worker thread.
	corrId := msg.GetCorrelationId()
	workerId, exists := ids[corrId]
	if exists && corrId != "" {
		// If this is a response, send it to the worker.
		err = workers.SendData(workerId, data)
		if err != nil {
			logger.Errorf(
				"Failed to send response with correlationd id %v to worker %v: %v",
				corrId, workerId, err,
			)
			return
		}
		logger.Debugf(
			"Routed message (%v) from validator to worker (%v)",
			corrId, workerId,
		)
		delete(ids, corrId)
		logger.Debugf("Removed (%v)->(%v) from map", corrId, workerId)
	} else {
		// If this is new, add it to the request queue
		queue <- msg
		logger.Debugf("Put %v (%v) on queue", msg.GetMessageType(), corrId)
	}
}

// Handle incoming messages from the workers
func receiveWorkers(ids map[string]string, validator, workers *messaging.Connection) {
	// Receive a mesasge from the workers
	workerId, data, err := workers.RecvData()
	if err != nil {
		logger.Errorf("Receiving message from workers failed: %v", err)
		return
	}

	msg, err := messaging.LoadMsg(data)
	if err != nil {
		logger.Errorf("Deserializing message from workers failed: %v", err)
		return
	}

	t := msg.GetMessageType()
	corrId := msg.GetCorrelationId()
	logger.Debugf("Got %v from worker (%v)", t, workerId)

	// Store which thread the response should be routed to
	if t != validator_pb2.Message_TP_PROCESS_RESPONSE {
		ids[corrId] = workerId
		logger.Debugf("Added (%v)->(%v) to map", corrId, workerId)
	}

	// Pass the message on to the validator
	err = validator.SendData("", data)
	if err != nil {
		logger.Errorf("Failed to send message (%v) to validator: %v", corrId, err)
		return
	}
	logger.Debugf("Sent message (%v) to validator", corrId)
}

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
			contextId, handler.FamilyName(), handler.FamilyVersion,
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

// Register a handler with the validator
func register(validator *messaging.Connection, handler TransactionHandler) error {
	regRequest := &processor_pb2.TpRegisterRequest{
		Family:     handler.FamilyName(),
		Version:    handler.FamilyVersion(),
		Encoding:   handler.Encoding(),
		Namespaces: handler.Namespaces(),
	}

	regRequestData, err := proto.Marshal(regRequest)
	if err != nil {
		return err
	}

	corrId, err := validator.SendNewMsg(
		validator_pb2.Message_TP_REGISTER_REQUEST,
		regRequestData,
	)
	if err != nil {
		return err
	}

	_, msg, err := validator.RecvMsg()
	if err != nil {
		return err
	}

	logger.Infof("Received %v", msg.MessageType)
	if msg.GetCorrelationId() != corrId {
		return fmt.Errorf("Mismatched Correlation Ids: %v != %v", msg.GetCorrelationId(), corrId)
	}

	if msg.GetMessageType() != validator_pb2.Message_TP_REGISTER_RESPONSE {
		return fmt.Errorf("Received unexpected message type: %v", msg.GetMessageType())
	}

	regResponse := &processor_pb2.TpRegisterResponse{}
	err = proto.Unmarshal(msg.GetContent(), regResponse)
	if err != nil {
		return err
	}

	if regResponse.GetStatus() != processor_pb2.TpRegisterResponse_OK {
		return fmt.Errorf("Got response: %v", regResponse.GetStatus())
	}
	logger.Infof(
		"Successfully registered handler (%v, %v, %v, %v)",
		handler.FamilyName(), handler.FamilyVersion,
		handler.Encoding(), handler.Namespaces(),
	)

	return nil
}
