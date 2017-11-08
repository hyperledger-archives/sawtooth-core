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
	"os"
	"os/signal"
	"runtime"
	"sawtooth_sdk/logging"
	"sawtooth_sdk/messaging"
	"sawtooth_sdk/protobuf/network_pb2"
	"sawtooth_sdk/protobuf/processor_pb2"
	"sawtooth_sdk/protobuf/validator_pb2"
)

var logger *logging.Logger = logging.Get()

const MAX_WORK_QUEUE_SIZE = 100

// TransactionProcessor is a generic class for communicating with a validator
// and routing transaction processing requests to a registered handler. It uses
// ZMQ and channels to handle requests concurrently.
type TransactionProcessor struct {
	uri      string
	context  *zmq.Context
	ids      map[string]string
	handlers []TransactionHandler
	nThreads int
	shutdown chan int
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
		shutdown: make(chan int),
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

	// Setup connection to internal worker thread pool
	workers, err := messaging.NewConnection(self.context, zmq.ROUTER, "inproc://workers")
	if err != nil {
		return fmt.Errorf("Could not create thread pool router: %v", err)
	}

	// Make work queue. Buffer so the router doesn't block
	queue := make(chan *validator_pb2.Message, MAX_WORK_QUEUE_SIZE)

	// Keep track of which correlation ids go to which worker threads, i.e. map
	// corrId->workerThreadId
	ids := make(map[string]string)

	// Startup worker thread pool
	for i := 0; i < self.nThreads; i++ {
		go worker(self.context, "inproc://workers", queue, self.handlers)
	}
	// Setup shutdown thread
	go shutdown(self.context, "inproc://workers", queue, self.shutdown)

	workersLeft := uint(self.nThreads) + 1

	// Setup ZMQ poller for routing messages between worker threads and validator
	poller := zmq.NewPoller()
	poller.Add(validator.Socket(), zmq.POLLIN)
	poller.Add(workers.Socket(), zmq.POLLIN)

	// Register all handlers with the validator
	for _, handler := range self.handlers {
		for _, version := range handler.FamilyVersions() {
			err := register(validator, handler, version, queue)
			if err != nil {
				return fmt.Errorf(
					"Error registering handler (%v, %v, %v): %v",
					handler.FamilyName(), version,
					handler.Namespaces(), err,
				)
			}
		}
	}

	// Poll for messages from worker threads or validator
	for {
		polled, err := poller.Poll(-1)
		if err != nil {
			return fmt.Errorf("Polling failed: %v", err)
		}
		for _, ready := range polled {
			switch socket := ready.Socket; socket {
			case validator.Socket():
				receiveValidator(ids, validator, workers, queue)

			case workers.Socket():
				receiveWorkers(ids, validator, workers, &workersLeft)
				if workersLeft == 0 {
					return nil
				}
			}
		}
	}
}

// Shutdown sends a message to the processor telling it to deregister.
func (self *TransactionProcessor) Shutdown() {
	// Initiate a clean shutdown
	self.shutdown <- 0
}

// ShutdownOnSignal sets up signal handling to shutdown the processor when one
// of the signals passed is received.
func (self *TransactionProcessor) ShutdownOnSignal(siglist ...os.Signal) {
	// Setup signal handlers
	ch := make(chan os.Signal)
	signal.Notify(ch, siglist...)

	go func() {
		// Wait for a signal
		_ = <-ch

		// Reset signal handlers
		signal.Reset(siglist...)
		logger.Warnf("Shutting down gracefully (Press Ctrl+C again to force)")

		self.Shutdown()
	}()
}

// Handle incoming messages from the validator
func receiveValidator(ids map[string]string, validator, workers messaging.Connection, queue chan *validator_pb2.Message) {
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
	t := msg.GetMessageType()
	corrId := msg.GetCorrelationId()

	// If this is a new request, put in on the work queue
	switch t {
	case validator_pb2.Message_TP_PROCESS_REQUEST:
		select {
		case queue <- msg:

		default:
			logger.Warnf("Work queue is full, denying request %v", corrId)
			data, err := proto.Marshal(&processor_pb2.TpProcessResponse{
				Status:  processor_pb2.TpProcessResponse_INTERNAL_ERROR,
				Message: "Work queue is full, denying request",
			})
			if err != nil {
				logger.Errorf(
					"Failed to notify validator the request is denied: %v", err,
				)
			}
			err = validator.SendMsg(
				validator_pb2.Message_TP_PROCESS_RESPONSE, data, corrId,
			)
			if err != nil {
				logger.Errorf(
					"Failed to notify validator the request is denied: %v", err,
				)
			}
		}
		return
	case validator_pb2.Message_PING_REQUEST:
		data, err := proto.Marshal(&network_pb2.PingResponse{})
		if err != nil {
			logger.Errorf(
				"Failed to respond to Ping %v", err,
			)
		}
		err = validator.SendMsg(
			validator_pb2.Message_PING_RESPONSE, data, corrId,
		)
		return
	}

	// If this is a response, send it to the worker.
	workerId, exists := ids[corrId]
	if exists && corrId != "" {
		err = workers.SendData(workerId, data)
		if err != nil {
			logger.Errorf(
				"Failed to send response with correlationd id %v to worker %v: %v",
				corrId, workerId, err,
			)
			return
		}
		delete(ids, corrId)
		return
	}

	logger.Warnf(
		"Received unexpected message from validator: (%v, %v)", t, corrId,
	)
}

// Handle incoming messages from the workers
func receiveWorkers(ids map[string]string, validator, workers messaging.Connection, workersLeft *uint) {
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

	if t == validator_pb2.Message_DEFAULT && corrId == "shutdown" {
		*workersLeft = *workersLeft - 1
		return
	}

	// Store which thread the response should be routed to
	if t != validator_pb2.Message_TP_PROCESS_RESPONSE {
		ids[corrId] = workerId
	}

	// Pass the message on to the validator
	err = validator.SendData("", data)
	if err != nil {
		logger.Errorf("Failed to send message (%v) to validator: %v", corrId, err)
		return
	}
}

// Register a handler with the validator
func register(validator messaging.Connection, handler TransactionHandler, version string, queue chan *validator_pb2.Message) error {
	regRequest := &processor_pb2.TpRegisterRequest{
		Family:     handler.FamilyName(),
		Version:    version,
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

	// The validator is impatient and will send requests before confirming
	// registration.
	var msg *validator_pb2.Message
	for {
		_, msg, err = validator.RecvMsg()
		if err != nil {
			return err
		}

		if msg.GetCorrelationId() != corrId {
			queue <- msg
		} else {
			break
		}
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
		"Successfully registered handler (%v, %v, %v)",
		handler.FamilyName(), version,
		handler.Namespaces(),
	)

	return nil
}
