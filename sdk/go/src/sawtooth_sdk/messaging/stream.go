package messaging

import (
	"fmt"
	"github.com/golang/protobuf/proto"
	zmq "github.com/pebbe/zmq4"
	uuid "github.com/satori/go.uuid"
	"sawtooth_sdk/protobuf/validator_pb2"
	"time"
)

const (
	SENDS_PER_LOOP  int           = 1
	POLLING_TIMEOUT time.Duration = 50 * time.Millisecond
)

type sendRequest struct {
	Msg        *validator_pb2.Message
	Response   chan *Response
	IsResponse bool
}

type Response struct {
	Msg *validator_pb2.Message
	Err error
}

type Stream struct {
	incoming  chan *validator_pb2.Message
	outgoing  chan interface{}
	context   *zmq.Context
	socket    *zmq.Socket
	identity  string
	url       string
	responses map[string]chan *Response
}

func NewStream() *Stream {
	return &Stream{
		incoming:  make(chan *validator_pb2.Message),
		outgoing:  make(chan interface{}),
		context:   nil,
		socket:    nil,
		identity:  generateId(),
		url:       "",
		responses: make(map[string]chan *Response),
	}
}

/* Connect the Stream using ZMQ and start a background thread. */
func (self *Stream) Connect(url string) error {
	self.url = url
	context, err := zmq.NewContext()
	if err != nil {
		return &CreateStreamError{
			fmt.Sprint("Failed to create ZMQ context: ", err),
		}
	}
	self.context = context

	go self.start()
	return nil
}

func (self *Stream) Close() {
	self.socket.Close()
	self.context.Term()
}

func (self *Stream) Send(t validator_pb2.Message_MessageType, c []byte) chan *Response {
	correlationId := generateId()
	msg := &validator_pb2.Message{
		MessageType:   t,
		CorrelationId: correlationId,
		Content:       c,
	}

	request := &sendRequest{
		Msg:        msg,
		Response:   make(chan *Response),
		IsResponse: false,
	}

	self.outgoing <- request

	return request.Response
}

func (self *Stream) Receive() (*validator_pb2.Message, error) {
	// TODO: Timeout?
	return <-self.incoming, nil
}

func (self *Stream) Respond(t validator_pb2.Message_MessageType, c []byte, corrId string) {
	msg := &validator_pb2.Message{
		MessageType:   t,
		CorrelationId: corrId,
		Content:       c,
	}

	request := &sendRequest{
		Msg:        msg,
		Response:   make(chan *Response),
		IsResponse: true,
	}

	self.outgoing <- request
}

func (self *Stream) start() {
	socket, err := self.context.NewSocket(zmq.DEALER)
	if err != nil {
		fmt.Sprint("Failed to create ZMQ socket: ", err)
		return
	}

	socket.SetIdentity(self.identity)
	fmt.Println("Socket Identity set to", self.identity)

	fmt.Printf("Connecting to %v...", self.url)
	err = socket.Connect(self.url)
	if err != nil {
		socket.Close()
		fmt.Sprint("Failed to connect to ", self.url, ": ", err)
		return
	}
	fmt.Println("done")
	self.socket = socket

	reactor := zmq.NewReactor()
	reactor.AddSocket(self.socket, zmq.POLLIN, self.receiver)
	reactor.AddChannel(self.outgoing, SENDS_PER_LOOP, self.sender)
	err = reactor.Run(POLLING_TIMEOUT)
	fmt.Println("Reactor exited:", err)
}

// Send messages from the outgoing channel in a loop
func (self *Stream) sender(i interface{}) error {
	req, ok := i.(*sendRequest)
	if !ok {
		fmt.Println("Received unexpected type from channel!")
		return nil
	}

	msgData, err := proto.Marshal(req.Msg)

	if err != nil {
		// TODO: Handle a panic in the event the channel is already closed
		req.Response <- &Response{
			Msg: nil,
			Err: &SendMsgError{fmt.Sprint("Failed to marshal:", err)},
		}
		close(req.Response)
	}

	err = sendBytes(self.socket, msgData)
	if err != nil {
		// TODO: Handle a panic in the event the channel is already closed
		req.Response <- &Response{
			Msg: nil,
			Err: &SendMsgError{fmt.Sprint("Failed to send message:", err)},
		}
		close(req.Response)
	}

	// Store the channel so the response can be sent on it
	if !req.IsResponse {
		self.responses[req.Msg.CorrelationId] = req.Response
	}
	return nil
}

// Receive messages in a loop and route
func (self *Stream) receiver(socketState zmq.State) error {
	// 1. Receive message
	bytes, err := recvBytes(self.socket)
	if err != nil {
		fmt.Println("Failed to received:", err)
		return nil
	}

	// 2. Deserialize
	msg := &validator_pb2.Message{}
	err = proto.Unmarshal(bytes, msg)
	if err != nil {
		fmt.Printf("Failed to unmarshal: %v\n", bytes)
		return nil
	}

	// 3. Route the message
	rc, exists := self.responses[msg.CorrelationId]
	fmt.Printf("rc: %v, exists: %v\n", rc, exists)

	//If this is a response, push it onto the response channel
	if exists && msg.CorrelationId != "" {
		fmt.Println("Got new response, sending on rc: ", msg.CorrelationId)
		// TODO: Handle a panic in the event the channel is already closed
		rc <- &Response{
			Msg: msg,
			Err: nil,
		}
		fmt.Println("Closing rc: ", msg.CorrelationId)
		close(rc)
		delete(self.responses, msg.CorrelationId)

	} else {
		fmt.Println("Got new message!")
		// TODO: Handle a panic in the event the channel is already closed
		self.incoming <- msg
	}
	return nil
}

func sendBytes(socket *zmq.Socket, bytes []byte) error {
	sent := 0
	for {
		n, err := socket.SendBytes(bytes, 0)
		if err != nil {
			return err
		}
		sent += n
		if sent == len(bytes) {
			break
		}
	}
	fmt.Printf("Sent %v bytes\n", sent)
	return nil
}

func recvBytes(socket *zmq.Socket) ([]byte, error) {
	recv := make([]byte, 0)
	for {
		bytes, err := socket.RecvBytes(0)
		if err != nil {
			return nil, err
		}
		recv = append(recv, bytes...)
		more, err := socket.GetRcvmore()
		if err != nil {
			return nil, err
		}
		if !more {
			break
		}
	}
	fmt.Printf("Received %v bytes\n", len(recv))
	return recv, nil
}

func generateId() string {
	return fmt.Sprint(uuid.NewV4())
}
