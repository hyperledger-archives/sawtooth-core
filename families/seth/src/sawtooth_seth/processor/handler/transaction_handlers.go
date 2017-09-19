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
	ptypes "burrow/permission/types"
	"encoding/hex"
	"fmt"
	"sawtooth_sdk/processor"
	. "sawtooth_seth/common"
	. "sawtooth_seth/protobuf/seth_pb2"
	"strings"
)

var TxnHandlers = map[SethTransaction_TransactionType]TransactionHandler{
	SethTransaction_CREATE_EXTERNAL_ACCOUNT: CreateExternalAccount,
	SethTransaction_CREATE_CONTRACT_ACCOUNT: CreateContractAccount,
	SethTransaction_MESSAGE_CALL:            MessageCall,
	SethTransaction_SET_PERMISSIONS:         SetPermissions,
}

func CreateExternalAccount(wrapper *SethTransaction, sender *EvmAddr, sapps *SawtoothAppState) HandlerResult {
	txn := wrapper.GetCreateExternalAccount()
	var newAcct *evm.Account

	// Sender is creating a separate external account, this is only possible
	// when gas is free and the sender has permission to create accounts
	if txn.GetTo() != nil {

		// The creating account must exist and have permission to create accounts
		senderAcct := sapps.GetAccount(sender.ToWord256())
		if senderAcct == nil {
			return HandlerResult{
				Error: &processor.InvalidTransactionError{Msg: fmt.Sprintf(
					"Creating account must already exist for it to be able to create other accounts: %v",
					sender,
				)},
			}
		}
		if !evm.HasPermission(sapps, senderAcct, ptypes.CreateAccount) {
			return HandlerResult{
				Error: &processor.InvalidTransactionError{Msg: fmt.Sprintf(
					"Sender account does not have permission to create external accounts: %v",
					sender,
				)},
			}
		}
		// Check that the nonce in the transaction matches the nonce in state
		if txn.GetNonce() != uint64(senderAcct.Nonce) {
			return HandlerResult{
				Error: &processor.InvalidTransactionError{Msg: fmt.Sprintf(
					"Nonces do not match: Transaction (%v), State (%v)",
					txn.GetNonce(), senderAcct.Nonce,
				)},
			}
		}

		// Get the address of the account to create
		newAcctAddr, err := NewEvmAddrFromBytes(txn.GetTo())
		if err != nil {
			return HandlerResult{
				Error: &processor.InvalidTransactionError{Msg: fmt.Sprintf(
					"Failed to construct address for new EOA: %v", txn.GetTo(),
				)},
			}
		}

		logger.Debugf("Creating new EOA on behalf of %v", newAcctAddr)

		// The new account must not already exist
		if sapps.GetAccount(newAcctAddr.ToWord256()) != nil {
			return HandlerResult{
				Error: &processor.InvalidTransactionError{Msg: fmt.Sprintf(
					"Account already exists at address %v", newAcctAddr,
				)},
			}
		}

		// If no permissions were passed by the transaction, inherit them from
		// sender. Otherwise, set them from transaction.
		var newPerms ptypes.AccountPermissions
		if txn.GetPermissions() == nil {
			newPerms = senderAcct.Permissions
			newPerms.Base.Set(ptypes.Root, false)

		} else {
			if !evm.HasPermission(sapps, senderAcct, ptypes.Root) {
				return HandlerResult{
					Error: &processor.InvalidTransactionError{Msg: fmt.Sprintf(
						"Creating account does not have permission to set permissions: %v",
						sender,
					)},
				}
			}
			newPerms = toVmPermissions(txn.GetPermissions())
		}

		// Create new account
		newAcct = &evm.Account{
			Address:     newAcctAddr.ToWord256(),
			Nonce:       1,
			Permissions: newPerms,
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
			return HandlerResult{
				Error: &processor.InvalidTransactionError{Msg: fmt.Sprintf(
					"Account already exists at address %v", sender,
				)},
			}
		}

		// Check global permissions to decide if the account can be created
		global := sapps.GetAccount(ptypes.GlobalPermissionsAddress256)

		// If global permissions have not been set yet, everything is allowed and
		// the account will have all permissions.
		var newPerms ptypes.AccountPermissions
		if global == nil {
			logger.Warnf("Global Permissions not set, all actions allowed!")
			newPerms.Base.Set(ptypes.AllPermFlags, true)

		} else {
			// If global permissions have been set, check the setting.
			if !evm.HasPermission(sapps, global, ptypes.CreateAccount) {
				return HandlerResult{
					Error: &processor.InvalidTransactionError{Msg: fmt.Sprintf(
						"New account creation is disabled, couldn't create account: %v",
						sender,
					)},
				}
			}

			// New account inherits global permissions except for Root
			newPerms = global.Permissions
			newPerms.Base.Set(ptypes.Root, false)
		}

		newAcct = &evm.Account{
			Address:     sender.ToWord256(),
			Nonce:       1,
			Permissions: newPerms,
		}

		sapps.UpdateAccount(newAcct)
	}

	return HandlerResult{
		NewAccount: newAcct,
	}
}

func CreateContractAccount(wrapper *SethTransaction, sender *EvmAddr, sapps *SawtoothAppState) HandlerResult {
	txn := wrapper.GetCreateContractAccount()

	// The creating account must already exist
	senderAcct := sapps.GetAccount(sender.ToWord256())
	if senderAcct == nil {
		return HandlerResult{
			Error: &processor.InvalidTransactionError{Msg: fmt.Sprintf(
				"Creating account must already exist to create contract account: %v",
				sender,
			)},
		}
	}

	// Verify this account has permission to create contract accounts
	if !evm.HasPermission(sapps, senderAcct, ptypes.CreateContract) {
		return HandlerResult{
			Error: &processor.InvalidTransactionError{Msg: fmt.Sprintf(
				"Sender account does not have permission to create contracts: %v",
				sender,
			)},
		}
	}

	// Check that the nonce in the transaction matches the nonce in state
	if txn.GetNonce() != uint64(senderAcct.Nonce) {
		return HandlerResult{
			Error: &processor.InvalidTransactionError{Msg: fmt.Sprintf(
				"Nonces do not match: Transaction (%v), State (%v)",
				txn.GetNonce(), senderAcct.Nonce,
			)},
		}
	}

	var newPerms ptypes.AccountPermissions
	if txn.GetPermissions() == nil {
		newPerms = senderAcct.Permissions
		newPerms.Base.Set(ptypes.Root, false)

	} else {
		if !evm.HasPermission(sapps, senderAcct, ptypes.Root) {
			return HandlerResult{
				Error: &processor.InvalidTransactionError{Msg: fmt.Sprintf(
					"Creating account does not have permission to set permissions: %v",
					sender,
				)},
			}
		}
		newPerms = toVmPermissions(txn.GetPermissions())
	}

	// Create the new account
	// NOTE: The senderAcct's nonce will be incremented
	newAcct := sapps.CreateAccount(senderAcct)

	// Initialize the new account
	out, gasUsed, err := callVm(sapps, newAcct, nil, txn.GetInit(), nil, txn.GetGasLimit())
	if err != nil {
		return HandlerResult{
			Error: &processor.InvalidTransactionError{Msg: err.Error()},
		}
	}
	newAcct.Nonce = 1
	newAcct.Code = out
	newAcct.Permissions = newPerms

	// Update accounts in state
	sapps.UpdateAccount(senderAcct)
	sapps.UpdateAccount(newAcct)

	return HandlerResult{
		GasUsed:     gasUsed,
		ReturnValue: out,
		NewAccount:  newAcct,
	}
}

func MessageCall(wrapper *SethTransaction, sender *EvmAddr, sapps *SawtoothAppState) HandlerResult {
	txn := wrapper.GetMessageCall()

	// The sender account must already exist
	senderAcct := sapps.GetAccount(sender.ToWord256())
	if senderAcct == nil {
		return HandlerResult{
			Error: &processor.InvalidTransactionError{Msg: fmt.Sprintf(
				"Sender account must already exist to message call: %v", sender,
			)},
		}
	}

	// Verify this account has permission to make message calls
	if !evm.HasPermission(sapps, senderAcct, ptypes.Call) {
		return HandlerResult{
			Error: &processor.InvalidTransactionError{Msg: fmt.Sprintf(
				"Sender account does not have permission to make message calls: %v",
				sender,
			)},
		}
	}

	// Check that the nonce in the transaction matches the nonce in state
	if txn.GetNonce() != uint64(senderAcct.Nonce) {
		return HandlerResult{
			Error: &processor.InvalidTransactionError{Msg: fmt.Sprintf(
				"Nonces do not match: Transaction (%v), State (%v)",
				txn.GetNonce(), senderAcct.Nonce,
			)},
		}
	}

	receiver, err := NewEvmAddrFromBytes(txn.GetTo())
	if err != nil {
		return HandlerResult{
			Error: &processor.InvalidTransactionError{Msg: fmt.Sprintf(
				"Failed to construct receiver address for message call: %v", txn.GetTo(),
			)},
		}
	}

	receiverAcct := sapps.GetAccount(receiver.ToWord256())

	// Receiving account must exist to call it
	if receiverAcct == nil {
		return HandlerResult{
			Error: &processor.InvalidTransactionError{Msg: fmt.Sprintf(
				"Receiver account must already exist to call it: %v", receiver,
			)},
		}
	}

	// Execute the contract
	out, gasUsed, err := callVm(sapps, senderAcct, receiverAcct, receiverAcct.Code,
		txn.GetData(), txn.GetGasLimit())
	if err != nil {
		return HandlerResult{
			Error: &processor.InvalidTransactionError{Msg: err.Error()},
		}
	}
	logger.Debug("Gas Used: ", gasUsed)
	logger.Debug("EVM Output: ", strings.ToLower(hex.EncodeToString(out)))

	senderAcct.Nonce += 1

	sapps.UpdateAccount(senderAcct)
	sapps.UpdateAccount(receiverAcct)

	return HandlerResult{
		ReturnValue: out,
		GasUsed:     gasUsed,
	}
}

func SetPermissions(wrapper *SethTransaction, sender *EvmAddr, sapps *SawtoothAppState) HandlerResult {
	txn := wrapper.GetSetPermissions()

	if txn.GetPermissions() == nil {
		return HandlerResult{
			Error: &processor.InvalidTransactionError{
				Msg: "Permissions field cannot be blank in UpdatePermissions transaction",
			},
		}
	}
	newPerms := toVmPermissions(txn.GetPermissions())

	// Get the account that is trying to update permissions
	senderAcct := sapps.GetAccount(sender.ToWord256())
	if senderAcct == nil {
		return HandlerResult{
			Error: &processor.InvalidTransactionError{Msg: fmt.Sprintf(
				"Sender account must already exist for updating permissions: %v", sender,
			)},
		}
	}

	// Verify this account has permission to update permissions
	if !evm.HasPermission(sapps, senderAcct, ptypes.Root) {
		return HandlerResult{
			Error: &processor.InvalidTransactionError{Msg: fmt.Sprintf(
				"Sender account does not have permission to change permissions: %v",
				sender,
			)},
		}
	}

	// Check that the nonce in the transaction matches the nonce in state
	if txn.GetNonce() != uint64(senderAcct.Nonce) {
		return HandlerResult{
			Error: &processor.InvalidTransactionError{Msg: fmt.Sprintf(
				"Nonces do not match: Transaction (%v), State (%v)",
				txn.GetNonce(), senderAcct.Nonce,
			)},
		}
	}

	receiver, err := NewEvmAddrFromBytes(txn.GetTo())
	if err != nil {
		return HandlerResult{
			Error: &processor.InvalidTransactionError{Msg: fmt.Sprintf(
				"Failed to construct receiver address for permission change: %v",
				txn.GetTo(),
			)},
		}
	}

	logger.Debugf(
		"SetPermissions(%v): Perms(%v), SetBit(%v)\n", receiver,
		newPerms.Base.Perms, newPerms.Base.SetBit,
	)

	receiverWord256 := receiver.ToWord256()
	receiverAcct := sapps.GetAccount(receiverWord256)
	if receiverAcct == nil {
		if receiverWord256 == ptypes.GlobalPermissionsAddress256 {
			receiverAcct = &evm.Account{
				Address: receiverWord256,
				Nonce:   1,
			}
		} else {
			return HandlerResult{
				Error: &processor.InvalidTransactionError{Msg: fmt.Sprintf(
					"Receiver account must already exist to change its permissions: %v",
					receiver,
				)},
			}
		}
	}

	// Update accounts
	senderAcct.Nonce += 1
	receiverAcct.Permissions = newPerms

	sapps.UpdateAccount(senderAcct)
	sapps.UpdateAccount(receiverAcct)

	return HandlerResult{}
}
