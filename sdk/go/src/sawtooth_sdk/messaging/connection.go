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

// Package messaging handles lower-level communication between a transaction
// processor and validator.
package messaging

import (
	"fmt"
	"github.com/golang/protobuf/proto"
	zmq "github.com/pebbe/zmq4"
	uuid "github.com/satori/go.uuid"
	"sawtooth_sdk/logging"
	"sawtooth_sdk/protobuf/validator_pb2"
)

var logger *logging.Logger = logging.Get()

// Generate a new UUID
func GenerateId() string {
	return fmt.Sprint(uuid.NewV4())
}

// DumpMsg serializes a validator message
func DumpMsg(t validator_pb2.Message_MessageType, c []byte, corrId string) ([]byte, error) {
	msg := &validator_pb2.Message{
		MessageType:   t,
		CorrelationId: corrId,
		Content:       c,
	}
	return proto.Marshal(msg)
}

// LoadMsg deserializes a validator message
func LoadMsg(data []byte) (msg *validator_pb2.Message, err error) {
	msg = &validator_pb2.Message{}
	err = proto.Unmarshal(data, msg)
	return
}

type Connection interface {
	SendData(id string, data []byte) error
	SendNewMsg(t validator_pb2.Message_MessageType, c []byte) (corrId string, err error)
	SendNewMsgTo(id string, t validator_pb2.Message_MessageType, c []byte) (corrId string, err error)
	SendMsg(t validator_pb2.Message_MessageType, c []byte, corrId string) error
	SendMsgTo(id string, t validator_pb2.Message_MessageType, c []byte, corrId string) error
	RecvData() (string, []byte, error)
	RecvMsg() (string, *validator_pb2.Message, error)
	RecvMsgWithId(corrId string) (string, *validator_pb2.Message, error)
	Close()
	Socket() *zmq.Socket
	Monitor(zmq.Event) (*zmq.Socket, error)
	Identity() string
}

// Connection wraps a ZMQ DEALER socket or ROUTER socket and provides some
// utility methods for sending and receiving messages.
type ZmqConnection struct {
	identity string
	uri      string
	socket   *zmq.Socket
	context  *zmq.Context
	incoming map[string]*storedMsg
}

type storedMsg struct {
	Id  string
	Msg *validator_pb2.Message
}

// NewConnection establishes a new connection using the given ZMQ context and
// socket type to the given URI.
func NewConnection(context *zmq.Context, t zmq.Type, uri string, bind bool) (*ZmqConnection, error) {
	socket, err := context.NewSocket(t)
	if err != nil {
		return nil, fmt.Errorf("Failed to create ZMQ socket: %v", err)
	}

	identity := GenerateId()
	socket.SetIdentity(identity)

	if bind {
		logger.Info("Binding to ", uri)
		err = socket.Bind(uri)
	} else {
		logger.Info("Connecting to ", uri)
		err = socket.Connect(uri)
	}
	if err != nil {
		return nil, fmt.Errorf("Failed to establish connection to %v: %v", uri, err)
	}

	return &ZmqConnection{
		identity: identity,
		uri:      uri,
		socket:   socket,
		context:  context,
		incoming: make(map[string]*storedMsg),
	}, nil
}

// SendData sends the byte array.
//
// If id is not "", the id is included as the first part of the message. This
// is useful for passing messages to a ROUTER socket so it can route them.
func (self *ZmqConnection) SendData(id string, data []byte) error {
	if id != "" {
		_, err := self.socket.SendMessage(id, [][]byte{data})
		if err != nil {
			return err
		}
	} else {
		_, err := self.socket.SendMessage([][]byte{data})
		if err != nil {
			return err
		}
	}
	return nil
}

// SendNewMsg creates a new validator message, assigns a new correlation id,
// serializes it, and sends it. It returns the correlation id created.
func (self *ZmqConnection) SendNewMsg(t validator_pb2.Message_MessageType, c []byte) (corrId string, err error) {
	return self.SendNewMsgTo("", t, c)
}

// SendNewMsgTo sends a new message validator message with the given id sent as
// the first part of the message. This is required when sending to a ROUTER
// socket, so it knows where to route the message.
func (self *ZmqConnection) SendNewMsgTo(id string, t validator_pb2.Message_MessageType, c []byte) (corrId string, err error) {
	corrId = GenerateId()
	return corrId, self.SendMsgTo(id, t, c, corrId)
}

// Send a message with the given correlation id
func (self *ZmqConnection) SendMsg(t validator_pb2.Message_MessageType, c []byte, corrId string) error {
	return self.SendMsgTo("", t, c, corrId)
}

// Send a message with the given correlation id and the prepends the id like
// SendNewMsgTo()
func (self *ZmqConnection) SendMsgTo(id string, t validator_pb2.Message_MessageType, c []byte, corrId string) error {
	data, err := DumpMsg(t, c, corrId)
	if err != nil {
		return err
	}

	return self.SendData(id, data)
}

// RecvData receives a ZMQ message from the wrapped socket and returns the
// identity of the sender and the data sent. If ZmqConnection does not wrap a
// ROUTER socket, the identity returned will be "".
func (self *ZmqConnection) RecvData() (string, []byte, error) {
	msg, err := self.socket.RecvMessage(0)

	if err != nil {
		return "", nil, err
	}
	switch len(msg) {
	case 1:
		data := []byte(msg[0])
		return "", data, nil
	case 2:
		id := msg[0]
		data := []byte(msg[1])
		return id, data, nil
	default:
		return "", nil, fmt.Errorf(
			"Receive message with unexpected length: %v", len(msg),
		)
	}
}

// RecvMsg receives a new validator message and returns it deserialized. If
// ZmqConnection wraps a ROUTER socket, id will be the identity of the sender.
// Otherwise, id will be "".
func (self *ZmqConnection) RecvMsg() (string, *validator_pb2.Message, error) {
	for corrId, stored := range self.incoming {
		delete(self.incoming, corrId)
		return stored.Id, stored.Msg, nil
	}

	// Receive a message from the socket
	id, bytes, err := self.RecvData()
	if err != nil {
		return "", nil, err
	}

	msg, err := LoadMsg(bytes)
	return id, msg, err
}

// RecvMsgWithId receives validator messages until a message with the given
// correlation id is found and returns this message. Any messages received that
// do not match the id are saved for subsequent receives.
func (self *ZmqConnection) RecvMsgWithId(corrId string) (string, *validator_pb2.Message, error) {
	// If the message is already stored, just return it
	stored, exists := self.incoming[corrId]
	if exists {
		return stored.Id, stored.Msg, nil
	}

	for {
		// If the message isn't stored, keep getting messages until it shows up
		id, bytes, err := self.RecvData()
		if err != nil {
			return "", nil, err
		}
		msg, err := LoadMsg(bytes)

		// If the ids match, return it
		if msg.GetCorrelationId() == corrId {
			return id, msg, err
		}

		// Otherwise, keep the message for later
		self.incoming[msg.GetCorrelationId()] = &storedMsg{Id: id, Msg: msg}
	}
}

// Close closes the wrapped socket. This should be called with defer() after opening the socket.
func (self *ZmqConnection) Close() {
	self.socket.Close()
}

// Socket returns the wrapped socket.
func (self *ZmqConnection) Socket() *zmq.Socket {
	return self.socket
}

// Create a new monitor socket pair and return the socket for listening
func (self *ZmqConnection) Monitor(events zmq.Event) (*zmq.Socket, error) {
	endpoint := fmt.Sprintf("inproc://monitor.%v", self.identity)
	err := self.socket.Monitor(endpoint, events)
	if err != nil {
		return nil, err
	}
	monitor, err := self.context.NewSocket(zmq.PAIR)
	err = monitor.Connect(endpoint)
	if err != nil {
		return nil, err
	}

	return monitor, nil
}

// Identity returns the identity assigned to the wrapped socket.
func (self *ZmqConnection) Identity() string {
	return self.identity
}
