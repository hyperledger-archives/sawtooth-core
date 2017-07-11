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
	evm "burrow/evm"
	. "burrow/word256"
	"encoding/hex"
	"fmt"
	"github.com/golang/protobuf/proto"
	. "sawtooth_burrow_evm/common"
	. "sawtooth_burrow_evm/protobuf/evm_pb2"
	"sawtooth_sdk/logging"
	"sawtooth_sdk/processor"
	"sawtooth_sdk/protobuf/processor_pb2"
	"sawtooth_sdk/protobuf/transaction_pb2"
)

type TransactionHandler func(*EvmTransaction, *EvmAddr, *SawtoothAppState) error

var logger *logging.Logger = logging.Get()

type BurrowEVMHandler struct{}

func NewBurrowEVMHandler() *BurrowEVMHandler {
	return &BurrowEVMHandler{}
}

func (self *BurrowEVMHandler) FamilyName() string {
	return FAMILY_NAME
}
func (self *BurrowEVMHandler) FamilyVersion() string {
	return FAMILY_VERSION
}
func (self *BurrowEVMHandler) Encoding() string {
	return ENCODING
}
func (self *BurrowEVMHandler) Namespaces() []string {
	return []string{PREFIX}
}

func (self *BurrowEVMHandler) Apply(request *processor_pb2.TpProcessRequest, state *processor.State) error {

	// Unpack and validate transaction
	wrapper, err := unpackPayload(request.GetPayload())
	if err != nil {
		return err
	}

	// Unpack and validate header
	header, err := unpackHeader(request.GetHeader())
	if err != nil {
		return err
	}

	// Retrieve the handler for this type of Burrow-EVM transaction
	handler, exists := TxnHandlers[wrapper.GetTransactionType()]
	if !exists {
		return &processor.InvalidTransactionError{Msg: fmt.Sprintf(
			"Unknown transaction type: %v", wrapper.GetTransactionType(),
		)}
	}

	// Construct address of sender. This is the address used by the EVM to
	// access the account.
	pubkey, decodeErr := hex.DecodeString(header.GetSignerPubkey())
	if decodeErr != nil {
		return &processor.InternalError{Msg: fmt.Sprintf(
			"Couldn't decode public key",
		)}
	}
	sender, err := PubToEvmAddr(pubkey)
	if err != nil {
		return &processor.InvalidTransactionError{Msg: fmt.Sprintf(
			"Couldn't determine sender from public key: %v", header.GetSignerPubkey(),
		)}
	}

	// Construct new state manager
	sapps := NewSawtoothAppState(state)

	// Call the handler
	return handler(wrapper, sender, sapps)
}

// -- utilities --

func callVm(sas *SawtoothAppState, sender, receiver *evm.Account,
	code, input []byte, gas uint64) ([]byte, error) {

	// Create EVM
	params := evm.Params{
		BlockHeight: 0,
		BlockHash:   Zero256,
		BlockTime:   0,
		GasLimit:    GAS_LIMIT,
	}
	vm := evm.NewVM(sas, params, Zero256, nil)

	// Convert the gas to a signed int to be compatible with the burrow EVM
	sGas := int64(gas)

	if receiver == nil {
		receiver = sender
	}

	output, err := vm.Call(sender, receiver, code, input, 0, &sGas)
	if err != nil {
		return nil, fmt.Errorf("EVM Error: %v", err)
	}
	return output, nil
}

func unpackPayload(payload []byte) (*EvmTransaction, error) {
	if payload == nil {
		return nil, &processor.InvalidTransactionError{
			Msg: "Request must contain payload",
		}
	}

	transaction := &EvmTransaction{}
	err := proto.Unmarshal(payload, transaction)
	if err != nil {
		return nil, &processor.InvalidTransactionError{
			Msg: "Malformed request payload",
		}
	}

	return transaction, nil
}

func unpackHeader(headerBytes []byte) (*transaction_pb2.TransactionHeader, error) {
	header := &transaction_pb2.TransactionHeader{}
	err := proto.Unmarshal(headerBytes, header)
	if err != nil {
		return nil, &processor.InvalidTransactionError{
			Msg: "Malformed request header",
		}
	}

	if header.GetSignerPubkey() == "" {
		return nil, &processor.InvalidTransactionError{Msg: "Public Key not set"}
	}

	return header, nil
}
