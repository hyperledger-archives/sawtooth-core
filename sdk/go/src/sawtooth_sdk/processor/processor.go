package processor

import (
	"fmt"
	"github.com/golang/protobuf/proto"
	"sawtooth_sdk/messaging"
	"sawtooth_sdk/protobuf/processor_pb2"
	"sawtooth_sdk/protobuf/transaction_pb2"
	"sawtooth_sdk/protobuf/validator_pb2"
)

// TransactionProcessor is a generic class for communicating with a validator
// and routing transaction processing requests to a registered handler.
type TransactionProcessor struct {
	url      string
	stream   *messaging.Stream
	handlers []TransactionHandler
}

func NewTransactionProcessor(url string) *TransactionProcessor {
	return &TransactionProcessor{
		url:      url,
		stream:   messaging.NewStream(),
		handlers: make([]TransactionHandler, 0),
	}
}

// Start connects the TransactionProcessor to a validator and starts listening
// for requests and routing them to an appropriate handler.
func (self *TransactionProcessor) Start() {
	// Connect and register with the validator
	err := self.stream.Connect(self.url)
	if err != nil {
		fmt.Println("Failed to start:", err)
		return
	}
	defer self.stream.Close()

	err = self.register()
	if err != nil {
		fmt.Println("Failed to register:", err)
		return
	}

	// Wait for messages
	for {
		msg, err := self.stream.Receive()
		if err != nil {
			// TODO: Handle timeout
			fmt.Println("Failed to receive a message")
			break
		}

		if msg.MessageType != validator_pb2.Message_TP_PROCESS_REQUEST {
			fmt.Println("Received unexpected message:", msg)
			break
		}

		request := &processor_pb2.TpProcessRequest{}
		err = proto.Unmarshal(msg.Content, request)
		if err != nil {
			fmt.Println("Failed to unmarshal:", err)
			break
		}

		header := &transaction_pb2.TransactionHeader{}
		err = proto.Unmarshal(request.Header, header)
		if err != nil {
			fmt.Println("Failed to unmarshal:", err)
			break
		}

		// Try to find a handler
		handler, err := self.findHandler(header)
		if err != nil {
			fmt.Println(err)
			break
		}

		// Construct new State instance for the handler
		contextId := request.GetContextId()
		state := NewState(self.stream, contextId)

		err = handler.Apply(request, state)

		// Process the handler response
		response := &processor_pb2.TpProcessResponse{}
		if err != nil {
			switch e := err.(type) {
			case *InvalidTransactionError:
				fmt.Println(e)
				response.Status =
					processor_pb2.TpProcessResponse_INVALID_TRANSACTION
			case *InternalError:
				fmt.Println(e)
				response.Status = processor_pb2.TpProcessResponse_INTERNAL_ERROR
			default:
				fmt.Println("Unknown error")
				response.Status = processor_pb2.TpProcessResponse_INTERNAL_ERROR
			}
		} else {
			response.Status = processor_pb2.TpProcessResponse_OK
		}

		responseData, err := proto.Marshal(response)
		if err != nil {
			fmt.Println("Failed to marshal:", err)
			break
		}

		// 6. Send back a response to the validator
		rc := <-self.stream.Respond(
			validator_pb2.Message_TP_PROCESS_RESPONSE,
			responseData, msg.CorrelationId,
		)

		if rc.Err != nil {
			fmt.Println("Error sending back response: ", err)
			break
		}
	}
}

// AddHandler adds the given handler to the TransactionProcessor so it can
// receive transaction processing requests. All handlers should be added prior
// to starting the processor.
func (self *TransactionProcessor) AddHandler(handler TransactionHandler) {
	self.handlers = append(self.handlers, handler)
}

// Searches for and returns a handler that matches the header. If a suitable
// handler is not found, returns an error.
func (self *TransactionProcessor) findHandler(header *transaction_pb2.TransactionHeader) (TransactionHandler, error) {
	for _, handler := range self.handlers {
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
	return nil, &UnknownHandlerError{fmt.Sprint(
		"Unknown handler: (%v, %v, %v)", header.GetFamilyName(),
		header.GetFamilyVersion(), header.GetPayloadEncoding(),
	)}
}

// Register all handlers with the validator
func (self *TransactionProcessor) register() error {
	for _, h := range self.handlers {
		err := self.regOne(
			h.FamilyName(), h.FamilyVersion(), h.Encoding(), h.Namespaces(),
		)
		if err != nil {
			return err
		}
	}
	return nil
}

// Register a handler with the validator
func (self *TransactionProcessor) regOne(name, ver, enc string, names []string) error {
	regRequest := &processor_pb2.TpRegisterRequest{
		Family:     name,
		Version:    ver,
		Encoding:   enc,
		Namespaces: names,
	}

	regRequestData, err := proto.Marshal(regRequest)
	if err != nil {
		return &RegistrationError{fmt.Sprint(err)}
	}

	response := <-self.stream.Send(
		validator_pb2.Message_TP_REGISTER_REQUEST,
		regRequestData,
	)

	if response.Err != nil {
		return &RegistrationError{fmt.Sprint(response.Err)}
	}

	msg := response.Msg

	fmt.Printf("Received (%v, %v)\n", msg.MessageType, msg.Content)
	if msg.GetMessageType() != validator_pb2.Message_TP_REGISTER_RESPONSE {
		return &RegistrationError{
			fmt.Sprint("Received unexpected message type:", msg.GetMessageType()),
		}
	}

	regResponse := &processor_pb2.TpRegisterResponse{}
	err = proto.Unmarshal(msg.GetContent(), regResponse)
	if err != nil {
		return &RegistrationError{fmt.Sprint(err)}
	}

	if regResponse.GetStatus() != processor_pb2.TpRegisterResponse_OK {
		return &RegistrationError{fmt.Sprint("Got response:", regResponse.GetStatus())}
	}
	fmt.Println("Registration successful")

	return nil
}

func in(val string, slice []string) bool {
	for _, i := range slice {
		if i == val {
			return true
		}
	}
	return false
}
