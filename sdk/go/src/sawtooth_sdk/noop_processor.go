package main

import (
	"fmt"
	"github.com/golang/protobuf/proto"
	zmq "github.com/pebbe/zmq4"
	"sawtooth_sdk/protobuf/processor"
	"sawtooth_sdk/protobuf/validator"
)

func main() {
	context, _ := zmq.NewContext()
	socket, _ := context.NewSocket(zmq.REQ)
	defer context.Term()
	defer socket.Close()

	endpoint := "tcp://localhost:40000"
	fmt.Printf("Connecting to %v...", endpoint)
	socket.Connect(endpoint)
	fmt.Println("done")

	// 1. Send registration request
	regRequest := &processor.TpRegisterRequest{
		Family:     "test_family",
		Version:    "1.0",
		Encoding:   "protobuf",
		Namespaces: []string{"test_namespace"},
	}
	regRequestData, err := proto.Marshal(regRequest)
	if err != nil {
		fmt.Printf("Failed to marshal: %v\n", err)
        return
	}

    correlationId := "123"
    msg := &validator.Message{
        MessageType: validator.Message_TP_REGISTER_REQUEST,
        CorrelationId: correlationId,
        Content: regRequestData,
    }
    msgData, err := proto.Marshal(msg)
	if err != nil {
		fmt.Printf("Failed to marshal: %v\n", err)
        return
	}
	socket.SendBytes(msgData, 0)
    fmt.Println("Sent register request")

	// 2. Get response
	msgData, _ = socket.RecvBytes(0)
	msg = &validator.Message{}
	err = proto.Unmarshal(msgData, msg)
	if err != nil {
		fmt.Printf("Failed to unmarshal: %v\n", msgData)
        return
	}

    if msg.MessageType != validator.Message_TP_REGISTER_RESPONSE {
		fmt.Printf("Received unexpected message type: %v\n", msg.MessageType)
        return
    }

    regResponse := &processor.TpRegisterResponse{}
    err = proto.Unmarshal(msg.Content, regResponse)
	if err != nil {
		fmt.Printf("Failed to unmarshal: %v\n", msg.Content)
        return
	}

	fmt.Printf("Register Response: %v\n", regResponse.Status)

    // 3. Send unregister request
	unRegRequest := &processor.TpUnregisterRequest{}
	unRegRequestData, err := proto.Marshal(unRegRequest)
	if err != nil {
		fmt.Printf("Failed to marshal: %v\n", err)
        return
	}

    correlationId = "456"
    msg = &validator.Message{
        MessageType: validator.Message_TP_UNREGISTER_REQUEST,
        CorrelationId: correlationId,
        Content: unRegRequestData,
    }
    msgData, err = proto.Marshal(msg)
	if err != nil {
		fmt.Printf("Failed to marshal: %v\n", err)
        return
	}
	socket.SendBytes(msgData, 0)

    // 4. Get response
	msgData, _ = socket.RecvBytes(0)
	msg = &validator.Message{}
	err = proto.Unmarshal(msgData, msg)
	if err != nil {
		fmt.Printf("Failed to unmarshal: %v\n", msgData)
        return
	}

    if msg.MessageType != validator.Message_TP_UNREGISTER_RESPONSE {
		fmt.Printf("Received unexpected message type: %v\n", msg.MessageType)
        return
    }

    unRegResponse := &processor.TpUnregisterResponse{}
    err = proto.Unmarshal(msg.Content, unRegResponse)
	if err != nil {
		fmt.Printf("Failed to unmarshal: %v\n", msg.Content)
        return
	}

	fmt.Printf("Unregister Response: %v\n", unRegResponse.Status)

}
