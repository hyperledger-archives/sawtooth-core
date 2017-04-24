package processor

import (
	"fmt"
	"github.com/golang/protobuf/proto"
	"sawtooth_sdk/messaging"
	"sawtooth_sdk/protobuf/state_context_pb2"
	"sawtooth_sdk/protobuf/validator_pb2"
)

type State struct {
	stream    *messaging.Stream
	contextId string
}

func NewState(stream *messaging.Stream, contextId string) *State {
	return &State{
		stream:    stream,
		contextId: contextId,
	}
}

func (self *State) Get(addresses []string) (map[string][]byte, error) {
	// 1. Construct the message
	request := &state_context_pb2.TpStateGetRequest{
		ContextId: self.contextId,
		Addresses: addresses,
	}
	bytes, err := proto.Marshal(request)
	if err != nil {
		return nil, &GetError{fmt.Sprint("Failed to marshal:", err)}
	}

	// 2. Send the message and get the response
	rc := <-self.stream.Send(
		validator_pb2.Message_TP_STATE_GET_REQUEST, bytes,
	)

	if rc.Err != nil {
		return nil, &GetError{fmt.Sprint("Failed to send get:", err)}
	}

	msg := rc.Msg

	if msg.GetMessageType() != validator_pb2.Message_TP_STATE_GET_RESPONSE {
		return nil, &GetError{
			fmt.Sprint("Expected TP_STATE_GET_RESPONSE but got", msg.GetMessageType()),
		}
	}

	// 4. Parse the result
	response := &state_context_pb2.TpStateGetResponse{}
	err = proto.Unmarshal(msg.GetContent(), response)
	if err != nil {
		return nil, &GetError{fmt.Sprint("Failed to unmarshal:", err)}
	}

	// Use a switch in case new Status values are added
	switch response.Status {
	case state_context_pb2.TpStateGetResponse_AUTHORIZATION_ERROR:
		return nil, &GetError{
			fmt.Sprint("Tried to get unauthorized address:", addresses),
		}
	}

	// 5. Construct and return a map
	results := make(map[string][]byte)
	for _, entry := range response.GetEntries() {
		results[entry.GetAddress()] = entry.GetData()
	}

	return results, nil
}

func (self *State) Set(pairs map[string][]byte) ([]string, error) {
	// 1. Construct the message
	entries := make([]*state_context_pb2.Entry, 0, len(pairs))
	for address, data := range pairs {
		entries = append(entries, &state_context_pb2.Entry{
			Address: address,
			Data:    data,
		})
	}

	request := &state_context_pb2.TpStateSetRequest{
		ContextId: self.contextId,
		Entries:   entries,
	}
	bytes, err := proto.Marshal(request)
	if err != nil {
		return nil, &SetError{fmt.Sprint("Failed to marshal:", err)}
	}

	// 2. Send the message and get the response
	rc := <-self.stream.Send(
		validator_pb2.Message_TP_STATE_SET_REQUEST, bytes,
	)

	if rc.Err != nil {
		return nil, &GetError{fmt.Sprint("Failed to send set:", err)}
	}

	msg := rc.Msg
	if msg.GetMessageType() != validator_pb2.Message_TP_STATE_SET_RESPONSE {
		return nil, &SetError{
			fmt.Sprint("Expected TP_STATE_SET_RESPONSE but got", msg.MessageType),
		}
	}

	// 4. Parse the result
	response := &state_context_pb2.TpStateSetResponse{}
	err = proto.Unmarshal(msg.Content, response)
	if err != nil {
		return nil, &SetError{fmt.Sprint("Failed to unmarshal:", err)}
	}

	// Use a switch in case new Status values are added
	switch response.GetStatus() {
	case state_context_pb2.TpStateSetResponse_AUTHORIZATION_ERROR:
		addresses := make([]string, 0, len(pairs))
		for a, _ := range pairs {
			addresses = append(addresses, a)
		}
		return nil, &SetError{
			fmt.Sprint("Tried to set unauthorized address:", addresses),
		}
	}

	return response.Addresses, nil
}
