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

const (
	MIN_VALUE       = 0
	MAX_VALUE       = 4294967295
	MAX_NAME_LENGTH = 20
	FAMILY_NAME     = "intkey"
)

func (self *IntkeyHandler) FamilyName() string {
	return FAMILY_NAME
}

func (self *IntkeyHandler) FamilyVersions() []string {
	return []string{"1.0"}
}

func (self *IntkeyHandler) Namespaces() []string {
	return []string{self.namespace}
}

func (self *IntkeyHandler) Apply(request *processor_pb2.TpProcessRequest, context *processor.Context) error {
	payloadData := request.GetPayload()
	if payloadData == nil {
		return &processor.InvalidTransactionError{Msg: "Must contain payload"}
	}
	var payload IntkeyPayload
	err := DecodeCBOR(payloadData, &payload)
	if err != nil {
		return &processor.InvalidTransactionError{
			Msg: fmt.Sprint("Failed to decode payload: ", err),
		}
	}

	if err != nil {
		logger.Error("Bad payload: ", payloadData)
		return &processor.InternalError{Msg: fmt.Sprint("Failed to decode payload: ", err)}
	}

	verb := payload.Verb
	name := payload.Name
	value := payload.Value

	if len(name) > MAX_NAME_LENGTH {
		return &processor.InvalidTransactionError{
			Msg: fmt.Sprintf(
				"Name must be a string of no more than %v characters",
				MAX_NAME_LENGTH),
		}
	}

	if value < MIN_VALUE {
		return &processor.InvalidTransactionError{
			Msg: fmt.Sprintf("Value must be >= %v, not: %v", MIN_VALUE, value),
		}
	}

	if value > MAX_VALUE {
		return &processor.InvalidTransactionError{
			Msg: fmt.Sprintf("Value must be <= %v, not: %v", MAX_VALUE, value),
		}
	}

	if !(verb == "set" || verb == "inc" || verb == "dec") {
		return &processor.InvalidTransactionError{Msg: fmt.Sprintf("Invalid verb: %v", verb)}
	}

	hashed_name := Hexdigest(name)
	address := self.namespace + hashed_name[len(hashed_name)-64:]

	results, err := context.GetState([]string{address})
	if err != nil {
		return err
	}

	var collisionMap map[string]int
	data, exists := results[address]
	if exists && len(data) > 0 {
		err = DecodeCBOR(data, &collisionMap)
		if err != nil {
			return &processor.InternalError{
				Msg: fmt.Sprint("Failed to decode data: ", err),
			}
		}
	} else {
		collisionMap = make(map[string]int)
	}

	var newValue int
	storedValue, exists := collisionMap[name]
	if verb == "inc" || verb == "dec" {
		if !exists {
			return &processor.InvalidTransactionError{Msg: "Need existing value for inc/dec"}
		}

		switch verb {
		case "inc":
			newValue = storedValue + value
		case "dec":
			newValue = storedValue - value
		}

		if newValue < MIN_VALUE {
			return &processor.InvalidTransactionError{
				Msg: fmt.Sprintf("New Value must be >= ", MIN_VALUE),
			}
		}

		if newValue > MAX_VALUE {
			return &processor.InvalidTransactionError{
				Msg: fmt.Sprintf("New Value must be <= ", MAX_VALUE),
			}
		}
	}

	if verb == "set" {
		if exists {
			return &processor.InvalidTransactionError{Msg: "Cannot set existing value"}
		}
		newValue = value
	}

	collisionMap[name] = newValue
	data, err = EncodeCBOR(collisionMap)
	if err != nil {
		return &processor.InternalError{
			Msg: fmt.Sprint("Failed to encode new map:", err),
		}
	}

	addresses, err := context.SetState(map[string][]byte{
		address: data,
	})
	if err != nil {
		return err
	}
	if len(addresses) == 0 {
		return &processor.InternalError{Msg: "No addresses in set response"}
	}

	return nil
}

func EncodeCBOR(value interface{}) ([]byte, error) {
	data, err := cbor.Dumps(value)
	return data, err
}

func DecodeCBOR(data []byte, pointer interface{}) error {
	defer func() error {
		if recover() != nil {
			return &processor.InvalidTransactionError{Msg: "Failed to decode payload"}
		}
		return nil
	}()
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
