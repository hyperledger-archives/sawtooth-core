package handler

import (
	"crypto/sha512"
	"encoding/hex"
	"fmt"
	cbor "github.com/brianolson/cbor_go"
	"sawtooth_sdk/logging"
	"sawtooth_sdk/processor"
	"sawtooth_sdk/protobuf/processor_pb2"
	"strings"
)

var logger *logging.Logger = logging.Get()

type IntkeyPayload struct {
	Verb  string
	Name  string
	Value int
}

type IntkeyHandler struct {
	namespace string
}

func NewIntkeyHandler(namespace string) *IntkeyHandler {
	return &IntkeyHandler{
		namespace: namespace,
	}
}

func (self *IntkeyHandler) FamilyName() string {
	return "intkey"
}
func (self *IntkeyHandler) FamilyVersion() string {
	return "1.0"
}
func (self *IntkeyHandler) Encoding() string {
	return "application/cbor"
}
func (self *IntkeyHandler) Namespaces() []string {
	return []string{self.namespace}
}

func (self *IntkeyHandler) Apply(request *processor_pb2.TpProcessRequest, state *processor.State) error {
	payloadData := request.GetPayload()
	if payloadData == nil {
		return &processor.InvalidTransactionError{"Must contain payload"}
	}

	var payload IntkeyPayload
	err := DecodeCBOR(payloadData, &payload)
	if err != nil {
		return &processor.InternalError{
			fmt.Sprint("Failed to decode payload: ", err),
		}
	}

	if err != nil {
		logger.Error("Bad payload: ", payloadData)
		return &processor.InternalError{fmt.Sprint("Failed to decode payload: ", err)}
	}

	verb := payload.Verb
	name := payload.Name
	value := payload.Value

	if value < 0 {
		return &processor.InvalidTransactionError{
			fmt.Sprint("Value must be >= 0, not: ", value),
		}
	}

	if !(verb == "set" || verb == "inc" || verb == "dec") {
		return &processor.InvalidTransactionError{fmt.Sprint("Invalid verb:", verb)}
	}

	address := self.namespace + Hexdigest(name)

	results, err := state.Get([]string{address})
	if err != nil {
		return &processor.InternalError{fmt.Sprint("Error getting state:", err)}
	}
	logger.Debug("Got: ", results)

	var collisionMap map[string]int
	data, exists := results[address]
	if exists && len(data) > 0 {
		logger.Debug("Decoding: ", data)
		err = DecodeCBOR(data, &collisionMap)
		if err != nil {
			return &processor.InternalError{
				fmt.Sprint("Failed to decode data: ", err),
			}
		}
	} else {
		collisionMap = make(map[string]int)
	}

	var newValue int
	storedValue, exists := collisionMap[name]
	if verb == "inc" || verb == "dec" {
		if !exists {
			return &processor.InvalidTransactionError{"Need existing value for inc/dec"}
		}

		switch verb {
		case "inc":
			newValue = storedValue + value
		case "dec":
			newValue = storedValue - value
		}
		if newValue < 0 {
			return &processor.InvalidTransactionError{"New Value must be >= 0"}
		}
	}

	if verb == "set" {
		if exists {
			return &processor.InvalidTransactionError{"Cannot set existing value"}
		}
		newValue = value
	}

	collisionMap[name] = newValue
	data, err = EncodeCBOR(collisionMap)
	if err != nil {
		return &processor.InternalError{
			fmt.Sprint("Failed to encode new map:", err),
		}
	}

	addresses, err := state.Set(map[string][]byte{
		address: data,
	})
	if err != nil {
		return &processor.InternalError{fmt.Sprint("Failed to set new Value:", err)}
	}
	if len(addresses) == 0 {
		return &processor.InternalError{"No addresses in set response"}
	}

	return nil
}

func EncodeCBOR(value interface{}) ([]byte, error) {
	data, err := cbor.Dumps(value)
	return data, err
}

func DecodeCBOR(data []byte, pointer interface{}) error {
	err := cbor.Loads(data, pointer)
	if err != nil {
		return err
	}
	return nil
}

func Hexdigest(str string) string {
	hash := sha512.New()
	hash.Write([]byte(str))
	hashBytes := hash.Sum(nil)
	return strings.ToLower(hex.EncodeToString(hashBytes))
}
