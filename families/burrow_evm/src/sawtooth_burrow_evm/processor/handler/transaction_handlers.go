/**
 * Copyright 2017 Intel Corporation
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *		 http://www.apache.org/licenses/LICENSE-2.0
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
	"encoding/hex"
	"fmt"
	. "sawtooth_burrow_evm/common"
	. "sawtooth_burrow_evm/protobuf/evm_pb2"
	"sawtooth_sdk/processor"
	"strings"
)

var TxnHandlers = map[EvmTransaction_TransactionType]TransactionHandler{
	EvmTransaction_CREATE_EXTERNAL_ACCOUNT: CreateExternalAccount,
	EvmTransaction_CREATE_CONTRACT_ACCOUNT: CreateContractAccount,
	EvmTransaction_MESSAGE_CALL:            MessageCall,
}

func CreateExternalAccount(wrapper *EvmTransaction, sender *EvmAddr, sapps *SawtoothAppState) error {
	txn := wrapper.GetCreateExternalAccount()

	// Sender is creating a separate external account, this is only possible
	// when gas is free and the sender has permission to create accounts
	if txn.GetTo() != nil {

		senderAcct := sapps.GetAccount(sender.ToWord256())
		if senderAcct == nil {
			return &processor.InvalidTransactionError{Msg: fmt.Sprintf(
				"Creating account must already exist for it to be able to create other accounts: %v",
				sender,
			)}
		}
		// Check that the nonce in the transaction matches the nonce in state
		if txn.GetNonce() != uint64(senderAcct.Nonce) {
			return &processor.InvalidTransactionError{Msg: fmt.Sprintf(
				"Nonces do not match: Transaction (%v), State (%v)",
				txn.GetNonce(), senderAcct.Nonce,
			)}
		}

		// Get the address of the account to create
		newAcctAddr, err := NewEvmAddrFromBytes(txn.GetTo())
		if err != nil {
			return &processor.InvalidTransactionError{Msg: fmt.Sprintf(
				"Failed to construct address for new EOA: %v", txn.GetTo(),
			)}
		}

		logger.Debugf("Creating new EOA on behalf of %v", newAcctAddr)

		// The new account must not already exist
		if sapps.GetAccount(newAcctAddr.ToWord256()) != nil {
			return &processor.InvalidTransactionError{Msg: fmt.Sprintf(
				"Account already exists at address %v", newAcctAddr,
			)}
		}

		// Create new account
		newAcct := &evm.Account{
			Address:     newAcctAddr.ToWord256(),
			Nonce:       1,
		}
		senderAcct.Nonce += 1

		// Update accounts in state
		sapps.UpdateAccount(senderAcct)
		sapps.UpdateAccount(newAcct)

		// Sender is new and is creating this account for the first time
	} else {
		logger.Debugf("Creating new EOA at sender address: %v", sender)

		// The new account must not already exist
		if sapps.GetAccount(sender.ToWord256()) != nil {
			return &processor.InvalidTransactionError{Msg: fmt.Sprintf(
				"Account already exists at address %v", sender,
			)}
		}

		newAcct := &evm.Account{
			Address:     sender.ToWord256(),
			Nonce:       1,
		}

		sapps.UpdateAccount(newAcct)
	}

	return nil
}

func CreateContractAccount(wrapper *EvmTransaction, sender *EvmAddr, sapps *SawtoothAppState) error {
	txn := wrapper.GetCreateContractAccount()

	// The creating account must already exist
	senderAcct := sapps.GetAccount(sender.ToWord256())
	if senderAcct == nil {
		return &processor.InvalidTransactionError{Msg: fmt.Sprintf(
			"Creating account must already exist to create contract account: %v",
			sender,
		)}
	}

	// Check that the nonce in the transaction matches the nonce in state
	if txn.GetNonce() != uint64(senderAcct.Nonce) {
		return &processor.InvalidTransactionError{Msg: fmt.Sprintf(
			"Nonces do not match: Transaction (%v), State (%v)",
			txn.GetNonce(), senderAcct.Nonce,
		)}
	}

	// Create the new account
	// NOTE: The senderAcct's nonce will be incremented
	newAcct := sapps.CreateAccount(senderAcct)

	// Initialize the new account
	out, err := callVm(sapps, newAcct, nil, txn.GetInit(), nil, txn.GetGasLimit())
	if err != nil {
		return &processor.InternalError{Msg: err.Error()}
	}
	newAcct.Nonce = 1
	newAcct.Code = out

	// Update accounts in state
	sapps.UpdateAccount(senderAcct)
	sapps.UpdateAccount(newAcct)

	return nil
}

func MessageCall(wrapper *EvmTransaction, sender *EvmAddr, sapps *SawtoothAppState) error {
	txn := wrapper.GetMessageCall()

	// The sender account must already exist
	senderAcct := sapps.GetAccount(sender.ToWord256())
	if senderAcct == nil {
		return &processor.InvalidTransactionError{Msg: fmt.Sprintf(
			"Sender account must already exist to message call: %v", sender,
		)}
	}

	// Check that the nonce in the transaction matches the nonce in state
	if txn.GetNonce() != uint64(senderAcct.Nonce) {
		return &processor.InvalidTransactionError{Msg: fmt.Sprintf(
			"Nonces do not match: Transaction (%v), State (%v)",
			txn.GetNonce(), senderAcct.Nonce,
		)}
	}

	receiver, err := NewEvmAddrFromBytes(txn.GetTo())
	if err != nil {
		return &processor.InvalidTransactionError{Msg: fmt.Sprintf(
			"Failed to construct receiver address for message call: %v", txn.GetTo(),
		)}
	}

	receiverAcct := sapps.GetAccount(receiver.ToWord256())

	// Receiving account must exist to call it
	if receiverAcct == nil {
		return &processor.InvalidTransactionError{Msg: fmt.Sprintf(
			"Receiver account must already exist to call it: %v", receiver,
		)}
	}

	// Execute the contract
	out, err := callVm(sapps, senderAcct, receiverAcct, receiverAcct.Code,
		txn.GetData(), txn.GetGasLimit())
	if err != nil {
		return &processor.InternalError{Msg: err.Error()}
	}
	logger.Debug("EVM Output: ", strings.ToLower(hex.EncodeToString(out)))

	senderAcct.Nonce += 1

	sapps.UpdateAccount(senderAcct)
	sapps.UpdateAccount(receiverAcct)

	return nil
}
