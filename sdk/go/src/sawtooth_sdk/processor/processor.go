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
	"time"
)

var logger *logging.Logger = logging.Get()

const DEFAULT_MAX_WORK_QUEUE_SIZE = 100

// TransactionProcessor is a generic class for communicating with a validator
// and routing transaction processing requests to a registered handler. It uses
// ZMQ and channels to handle requests concurrently.
type TransactionProcessor struct {
	uri         string
	ids         map[string]string
	handlers    []TransactionHandler
	nThreads    uint
	maxQueue    uint
	shutdown_tx messaging.Connection
}

// NewTransactionProcessor initializes a new Transaction Process and points it
// at the given URI. If it fails to initialize, it will panic.
func NewTransactionProcessor(uri string) *TransactionProcessor {
	return &TransactionProcessor{
		uri:         uri,
		ids:         make(map[string]string),
		handlers:    make([]TransactionHandler, 0),
		nThreads:    uint(runtime.GOMAXPROCS(0)),
		maxQueue:    DEFAULT_MAX_WORK_QUEUE_SIZE,
		shutdown_tx: nil,
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
func (self *TransactionProcessor) SetThreadCount(n uint) {
	self.nThreads = n
}

func (self *TransactionProcessor) SetMaxQueueSize(n uint) {
	self.maxQueue = n
}

// Start connects the TransactionProcessor to a validator and starts listening
// for requests and routing them to an appropriate handler.
func (self *TransactionProcessor) Start() error {
	for {
		context, err := zmq.NewContext()
		if err != nil {
			panic(fmt.Sprint("Failed to create ZMQ context: ", err))
		}
		reconnect, err := self.start(context)
		if err != nil {
			return err
		}
		// If the validator disconnected, then start() returns true
		if !reconnect {
			break
		}
	}
	return nil
}

func (self *TransactionProcessor) start(context *zmq.Context) (bool, error) {
	restart := false

	// Establish a connection to the validator
	validator, err := messaging.NewConnection(context, zmq.DEALER, self.uri, false)
	if err != nil {
		return restart, fmt.Errorf("Could not connect to validator: %v", err)
	}

	monitor, err := validator.Monitor(zmq.EVENT_DISCONNECTED)
	if err != nil {
		return restart, fmt.Errorf("Could not monitor validator connection: %v", err)
	}

	// Setup connection to internal worker thread pool
	workers, err := messaging.NewConnection(context, zmq.ROUTER, "inproc://workers", true)
	if err != nil {
		return restart, fmt.Errorf("Could not create thread pool router: %v", err)
	}

	// Setup shutdown listening socket
	shutdown_rx, err := messaging.NewConnection(context, zmq.PAIR, "inproc://shutdown", true)
	if err != nil {
		return restart, fmt.Errorf("Could not create shutdown connection: %v", err)
	}
	self.shutdown_tx, err = messaging.NewConnection(context, zmq.PAIR, "inproc://shutdown", false)

	// Make work queue. Buffer so the router doesn't block
	queue := make(chan *validator_pb2.Message, self.maxQueue)

	// Make done channel for tracking thread shutdown
	workers_done := make(chan bool, self.nThreads)

	// Keep track of which correlation ids go to which worker threads, i.e. map
	// corrId->workerThreadId
	ids := make(map[string]string)

	// Startup worker thread pool
	for i := uint(0); i < self.nThreads; i++ {
		go worker(context, "inproc://workers", queue, workers_done, self.handlers)
	}

	// Register all handlers with the validator
	for _, handler := range self.handlers {
		for _, version := range handler.FamilyVersions() {
			logger.Debugf(
				"Registering (%v, %v, %v)",
				handler.FamilyName(),
				version,
				handler.Namespaces())
			err := register(validator, shutdown_rx, handler, version, queue, uint32(self.maxQueue))
			if err != nil {
				return restart, fmt.Errorf(
					"Error registering handler (%v, %v, %v): %v",
					handler.FamilyName(), version,
					handler.Namespaces(), err,
				)
			}
		}
	}

	// Setup ZMQ poller for routing messages between worker threads and validator
	poller := zmq.NewPoller()
	poller.Add(validator.Socket(), zmq.POLLIN)
	poller.Add(monitor, zmq.POLLIN)
	poller.Add(workers.Socket(), zmq.POLLIN)
	poller.Add(shutdown_rx.Socket(), zmq.POLLIN)

	// Poll for messages from worker threads or validator
	for {
		polled, err := poller.Poll(-1)
		if err != nil {
			return restart, fmt.Errorf("Polling failed: %v", err)
		}
		for _, ready := range polled {
			switch socket := ready.Socket; socket {
			case validator.Socket():
				receiveValidator(ids, validator, workers, queue)

			case monitor:
				restart = receiveMonitor(monitor, self.shutdown_tx)

			case workers.Socket():
				receiveWorkers(ids, validator, workers)

			case shutdown_rx.Socket():
				restart = receiveShutdown(queue, self.nThreads, workers_done, shutdown_rx, validator, workers, monitor)
				return restart, nil
			}
		}
	}
}

// Shutdown sends a message to the processor telling it to deregister.
func (self *TransactionProcessor) Shutdown() {
	// Initiate a clean shutdown
	if self.shutdown_tx != nil {
		err := self.shutdown_tx.SendData("", []byte("shutdown"))
		if err != nil {
			logger.Errorf("Failed to send restart command")
		}
	}
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

// Handle monitor events
func receiveMonitor(monitor *zmq.Socket, shutdown messaging.Connection) bool {
	restart := false
	event, endpoint, _, err := monitor.RecvEvent(0)
	if err != nil {
		logger.Error(err)
	} else {
		if event == zmq.EVENT_DISCONNECTED {
			logger.Infof("Validator '%v' disconnected", endpoint)
			restart = true
		} else {
			logger.Errorf("Received unexpected event on monitor socket: %v", event)
		}
		err = shutdown.SendData("", []byte("restart"))
		if err != nil {
			logger.Errorf("Failed to send restart command")
		}
	}
	return restart
}

// Handle incoming messages from the workers
func receiveWorkers(ids map[string]string, validator, workers messaging.Connection) {
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

// Handle shutdown
func receiveShutdown(queue chan *validator_pb2.Message, worker_count uint, done <-chan bool, shutdown_rx, validator, workers messaging.Connection, monitor *zmq.Socket) bool {
	_, data, err := shutdown_rx.RecvData()
	if err != nil {
		logger.Errorf("Error receiving shutdown: %v", err)
	}

	restart := false
	cmd := string(data)
	if cmd == "restart" {
		restart = true
	} else if cmd != "shutdown" {
		fmt.Errorf("Received unexpected shutdown command: %v", cmd)
		return false
	}

	logger.Infof("Received command to %v", cmd)
	err = shutdown(queue, worker_count, done, shutdown_rx, validator, workers, monitor, restart)
	if err != nil {
		logger.Errorf("Error shutting down: %v", err)
		return false
	}
	return restart
}

func shutdown(queue chan *validator_pb2.Message, worker_count uint, workers_done <-chan bool, shutdown_rx, validator, workers messaging.Connection, monitor *zmq.Socket, force bool) error {
	// Close the work queue, telling the worker threads there's no more work
	close(queue)

	// Close the workers connection, causing any workers that try to send/recv
	// to get an error
	workers.Close()

	// Close the monitor socket
	monitor.Close()

	if !force {
		// Send a request to be unregistered
		data, err := proto.Marshal(&processor_pb2.TpUnregisterRequest{})
		if err != nil {
			logger.Errorf(
				"Failed to unregister: %v", err,
			)
		}
		corrId, err := validator.SendNewMsg(
			validator_pb2.Message_TP_UNREGISTER_REQUEST, data,
		)
		if err != nil {
			logger.Errorf(
				"Failed to unregister: %v", err,
			)
		}

		// Wait for a response, or timeout
		unregistered := make(chan bool, 1)
		go func() {
			_, msg, err := validator.RecvMsgWithId(corrId)
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
		}()

		select {
		case <-unregistered:
			logger.Infof("Unregister successful")
		case <-time.After(3 * time.Second):
			logger.Warnf("Waiting for unregister response timed out")
		}

	}

	validator.Close()
	shutdown_rx.Close()

	// Wait for worker threads to die
	for i := uint(0); i < worker_count; i++ {
		logger.Debugf("Workers done %v/%v", i, worker_count)
		<-workers_done
	}
	logger.Debugf("Workers done %v/%v", worker_count, worker_count)

	return nil
}

// Register a handler with the validator
func register(validator, shutdown_rx messaging.Connection, handler TransactionHandler, version string, queue chan *validator_pb2.Message, maxOccupancy uint32) error {
	regRequest := &processor_pb2.TpRegisterRequest{
		Family:       handler.FamilyName(),
		Version:      version,
		Namespaces:   handler.Namespaces(),
		MaxOccupancy: maxOccupancy,
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

	// Need to also watch the shutdown socket so we can abort registration
	poller := zmq.NewPoller()
	poller.Add(validator.Socket(), zmq.POLLIN)
	poller.Add(shutdown_rx.Socket(), zmq.POLLIN)

	for {
		polled, err := poller.Poll(-1)
		if err != nil {
			return fmt.Errorf("Polling failed: %v", err)
		}
		for _, ready := range polled {
			switch socket := ready.Socket; socket {
			case validator.Socket():
				var msg *validator_pb2.Message
				_, msg, err = validator.RecvMsg()
				if err != nil {
					return err
				}

				// The validator is impatient and will send requests before confirming
				// registration.
				if msg.GetCorrelationId() != corrId {
					queue <- msg
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

			case shutdown_rx.Socket():
				return fmt.Errorf("Received shutdown while registering")
			}
		}
	}
}
