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
	"sawtooth_sdk/client"
	"sawtooth_sdk/logging"
	"sawtooth_sdk/processor"
	"sawtooth_sdk/protobuf/processor_pb2"
	"sawtooth_sdk/protobuf/transaction_pb2"
	"strings"
)

const (
	GAS_LIMIT = 1 << 31
)

var logger *logging.Logger = logging.Get()

type BurrowEVMHandler struct{}

func NewBurrowEVMHandler() *BurrowEVMHandler {
	return &BurrowEVMHandler{}
}

func (self *BurrowEVMHandler) FamilyName() string {
	return "burrow-evm"
}
func (self *BurrowEVMHandler) FamilyVersion() string {
	return "1.0"
}
func (self *BurrowEVMHandler) Encoding() string {
	return "application/protobuf"
}
func (self *BurrowEVMHandler) Namespaces() []string {
	return []string{PREFIX}
}

func (self *BurrowEVMHandler) Apply(request *processor_pb2.TpProcessRequest, state *processor.State) error {

	// Unpack and validate transaction
	transaction, err := unpackPayload(request.GetPayload())
	if err != nil {
		return err
	}

	// Unpack and validate header
	header, err := unpackHeader(request.GetHeader())
	if err != nil {
		return err
	}

	// Construct address of sender. This is the address used by the EVM to
	// access the account.
	senderAddress, _ := PubToEvmAddr(client.MustDecode(header.GetSignerPubkey()))
	sm := NewStateManager(state)

	if transaction.GetTo() == nil {
		err = loadAccount(senderAddress, transaction, sm)
	} else {
		err = execAccount(senderAddress, transaction, sm)
	}
	if err != nil {
		return err
	}

	return nil
}

func loadAccount(senderAddress *EvmAddr, txn *EvmTransaction, sm *StateManager) error {

	// Load the entry for the sender from global state
	senderEntry, err := sm.GetEntry(senderAddress)
	if err != nil {
		return &processor.InternalError{Msg: err.Error()}
	}

	// If the sender entry doesn't already exist, this is a new Externally Owned
	// Account and it will be created at the sender's address.
	if senderEntry == nil {
		return createEoaAccount(senderAddress, txn, sm)
	}

	// If the entry does already exist, this is a new Contract Account and it
	// will be created at a new address derived from the existing account.
	return createContractAccount(senderAddress, senderEntry, txn, sm)
}

func createEoaAccount(address *EvmAddr, txn *EvmTransaction, sm *StateManager) error {
	logger.Debugf("Creating new EOA")
	if txn.GetNonce() != 0 {
		return &processor.InvalidTransactionError{
			Msg: "Nonce must be 0 when creating new Externally Owned Account",
		}
	}

	if txn.GetInit() != nil {
		return &processor.InvalidTransactionError{Msg: fmt.Sprintf(
			"EOAs cannot have code associated with them.",
		)}
	}

	entry, err := sm.NewEntry(address)
	if err != nil {
		return &processor.InternalError{Msg: fmt.Sprintf(
			"Couldn't create account at %v: %v", address, err,
		)}
	}

	entry.GetAccount().Nonce = 1
	err = sm.SetEntry(address, entry)
	if err != nil {
		return &processor.InternalError{Msg: fmt.Sprintf(
			"Couldn't set new account nonce %v: %v", address, err,
		)}
	}

	return nil
}

func createContractAccount(senderAddress *EvmAddr, senderEntry *EvmEntry, txn *EvmTransaction, sm *StateManager) error {
	logger.Debugf("Creating new CA")
	senderAccount := toVmAccount(senderEntry.GetAccount())
	if senderAccount == nil {
		return &processor.InternalError{Msg: fmt.Sprintf(
			"Entry exists but no account (%v)", senderEntry,
		)}
	}

	// Check that the nonce in the transaction matches expected nonce
	if txn.GetNonce() != uint64(senderAccount.Nonce) {
		return &processor.InvalidTransactionError{Msg: fmt.Sprintf(
			"Nonces do not match: Transaction (%v), State (%v)",
			txn.GetNonce(), senderAccount.Nonce,
		)}
	}

	newEntryAddress := senderAddress.Derive(uint64(senderAccount.Nonce))
	newEntry, err := sm.NewEntry(newEntryAddress)

	if err != nil {
		return &processor.InternalError{Msg: fmt.Sprintf(
			"Couldn't create account at %v: %v",
			newEntryAddress, err,
		)}
	}

	// If code was supplied, run it and set the account's code to the
	// output.
	if txn.GetInit() != nil {
		newVmAccount := toVmAccount(newEntry.GetAccount())

		init := txn.GetInit()[:]
		gas := txn.GetGasLimit()

		out, err := callVm(sm, newVmAccount, nil, init, nil, gas)
		if err != nil {
			return &processor.InternalError{Msg: err.Error()}
		}
		newVmAccount.Code = out

		newEntry.Account = toStateAccount(newVmAccount)
		err = sm.SetEntry(newEntryAddress, newEntry)

		if err != nil {
			return &processor.InternalError{Msg: fmt.Sprintf(
				"Couldn't create account at %v: %v",
				newEntryAddress, err,
			)}
		}
	}

	senderAccount.Nonce += 1
	senderEntry.Account = toStateAccount(senderAccount)
	err = sm.SetEntry(senderAddress, senderEntry)
	if err != nil {
		return &processor.InternalError{Msg: fmt.Sprintf(
			"Couldn't update account nonce at %v: %v",
			senderAddress, err,
		)}
	}

	return nil
}

func execAccount(senderAddress *EvmAddr, txn *EvmTransaction, sm *StateManager) error {

	// Load the entry of the sender from global state
	senderEntry, err := sm.GetEntry(senderAddress)
	if err != nil {
		return &processor.InternalError{Msg: err.Error()}
	}
	senderAccount := toVmAccount(senderEntry.GetAccount())

	if senderEntry == nil || senderAccount == nil {
		return &processor.InvalidTransactionError{Msg: fmt.Sprintf(
			"Message call from non-existent account (%v)", senderAddress,
		)}
	}

	// Check that the nonce in the transaction matches expected nonce
	if txn.GetNonce() != uint64(senderAccount.Nonce) {
		return &processor.InvalidTransactionError{Msg: fmt.Sprintf(
			"Nonces do not match: Transaction (%v), State (%v)",
			txn.GetNonce(), senderAccount.Nonce,
		)}
	}

	// Load the entry of the contract to be called from global state
	receiverAddress, err := NewEvmAddrFromBytes(txn.GetTo())
	if err != nil {
		return &processor.InvalidTransactionError{Msg: fmt.Sprintf(
			"Invalid 'to' address %v: %v", txn.GetTo(), err.Error(),
		)}
	}
	receiverEntry, err := sm.GetEntry(receiverAddress)
	if err != nil {
		return &processor.InvalidTransactionError{Msg: err.Error()}
	}
	receiverAccount := toVmAccount(receiverEntry.GetAccount())

	if receiverEntry == nil || receiverAccount == nil {
		return &processor.InvalidTransactionError{Msg: fmt.Sprintf(
			"Call to non-existent account (%v)", txn.GetTo(),
		)}
	}

	code := receiverAccount.Code
	data := txn.GetData()[:]
	gas := txn.GetGasLimit()

	// Run the contract
	out, err := callVm(sm, senderAccount, receiverAccount, code, data, gas)
	if err != nil {
		return &processor.InternalError{Msg: err.Error()}
	}

	logger.Debug("EVM Output: ", strings.ToLower(hex.EncodeToString(out)))

	// Increment the sender's nonce
	senderAccount.Nonce += 1
	senderEntry.Account = toStateAccount(senderAccount)
	err = sm.SetEntry(senderAddress, senderEntry)
	if err != nil {
		return &processor.InternalError{Msg: fmt.Sprintf(
			"Couldn't update account nonce at %v: %v",
			senderAddress, err,
		)}
	}
	return nil
}

// ---

func callVm(sm *StateManager, sender, receiver *evm.Account, code, input []byte, gas uint64) ([]byte, error) {

	sas := NewSawtoothAppState(sm)

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
	return vm.Call(sender, receiver, code, input, 0, &sGas)
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
