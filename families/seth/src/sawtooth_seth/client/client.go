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

package client

import (
	"bytes"
	"encoding/base64"
	"fmt"
	"github.com/golang/protobuf/proto"
	"net/http"
	sdk "sawtooth_sdk/client"
	"sawtooth_sdk/logging"
	. "sawtooth_seth/common"
	. "sawtooth_seth/protobuf/seth_pb2"
)

var logger *logging.Logger = logging.Get()

type Client struct {
	Url string
}

func New(url string) *Client {
	return &Client{
		Url: url,
	}
}

// Get retrieves all data in state associated with the given address. If there
// isn't anything at the address, returns nil.
func (c *Client) Get(address []byte) (*EvmEntry, error) {
	evmAddr, err := NewEvmAddrFromBytes(address)
	if err != nil {
		return nil, err
	}

	resp, err := http.Get(c.Url + "/state/" + evmAddr.ToStateAddr().String())
	if err != nil {
		return nil, err
	}

	body, err := ParseRespBody(resp)
	if err != nil {
		return nil, err
	}

	var data string
	if body.Data != nil {
		data = body.Data.(string)
	}

	buf, err := base64.StdEncoding.DecodeString(data)
	if err != nil {
		return nil, err
	}

	if len(buf) == 0 {
		return nil, nil
	}
	entry := &EvmEntry{}
	err = proto.Unmarshal(buf, entry)
	if err != nil {
		return nil, err
	}

	return entry, nil
}

// CreateExternalAccount submits a transaction to create the account with the
// given private key. If moderator is not nil, the account associated with that
// key will be used to create the new account. If perms is not nil, the new
// account is created with the given permissions.
//
// Returns the address of the new account.
func (c *Client) CreateExternalAccount(priv, moderator []byte, perms *EvmPermissions, nonce uint64, wait int) ([]byte, error) {
	newAcctAddr, err := PrivToEvmAddr(priv)
	if err != nil {
		return nil, err
	}

	transaction := &SethTransaction{
		TransactionType: SethTransaction_CREATE_EXTERNAL_ACCOUNT,
		CreateExternalAccount: &CreateExternalAccountTxn{
			Permissions: perms,
			Nonce:       nonce,
		},
	}

	addresses := []string{
		newAcctAddr.ToStateAddr().String(),
		// For checking global permissions
		GlobalPermissionsAddress().ToStateAddr().String(),
	}

	// The account being created is not the creating account
	sender := priv
	if moderator != nil {
		sender = moderator
		moderatorAddr, err := PrivToEvmAddr(moderator)
		if err != nil {
			return nil, err
		}
		addresses = append(addresses, moderatorAddr.ToStateAddr().String())
		transaction.CreateExternalAccount.To = newAcctAddr.Bytes()
	}

	encoder := sdk.NewEncoder(sender, sdk.TransactionParams{
		FamilyName:      FAMILY_NAME,
		FamilyVersion:   FAMILY_VERSION,
		PayloadEncoding: ENCODING,
		Inputs:          addresses,
		Outputs:         addresses,
	})

	body, err := c.sendTxn(transaction, encoder, wait)
	if err != nil {
		return nil, err
	}
	logger.Debug(body)

	return newAcctAddr.Bytes(), nil
}

// CreateContractAccount creates a new contract associated with the account
// associated with the given private key. The account is initialized with the
// data in init. If permissions are passed, the account is created with those
// permissions.
//
// Returns the address of the new account.
func (c *Client) CreateContractAccount(priv []byte, init []byte, perms *EvmPermissions, nonce uint64, gas uint64, wait int) ([]byte, error) {
	creatorAcctAddr, err := PrivToEvmAddr(priv)
	if err != nil {
		return nil, err
	}

	newAcctAddr := creatorAcctAddr.Derive(nonce)

	addresses := []string{
		creatorAcctAddr.ToStateAddr().String(),
		newAcctAddr.ToStateAddr().String(),
		// For checking global permissions
		GlobalPermissionsAddress().ToStateAddr().String(),
	}

	encoder := sdk.NewEncoder(priv, sdk.TransactionParams{
		FamilyName:      FAMILY_NAME,
		FamilyVersion:   FAMILY_VERSION,
		PayloadEncoding: ENCODING,
		Inputs:          addresses,
		Outputs:         addresses,
	})

	transaction := &SethTransaction{
		TransactionType: SethTransaction_CREATE_CONTRACT_ACCOUNT,
		CreateContractAccount: &CreateContractAccountTxn{
			Nonce:       nonce,
			GasLimit:    gas,
			Init:        init,
			Permissions: perms,
		},
	}

	body, err := c.sendTxn(transaction, encoder, wait)
	if err != nil {
		return nil, err
	}
	logger.Debug(body)

	return newAcctAddr.Bytes(), nil
}

// MessageCall sends a message call from the account associated with the given
// private key to the account at the address to. data is used as the input
// to the contract call.
//
// Returns the output from the EVM call.
func (c *Client) MessageCall(priv, to, data []byte, nonce uint64, gas uint64, wait int, chaining_enabled bool) ([]byte, error) {
	fromAddr, err := PrivToEvmAddr(priv)
	if err != nil {
		return nil, err
	}

	toAddr, err := NewEvmAddrFromBytes(to)
	if err != nil {
		return nil, err
	}

	var addresses []string
	if chaining_enabled {
		addresses = append(addresses, PREFIX)
	} else {
		addresses = append(addresses,
			fromAddr.ToStateAddr().String(),
			toAddr.ToStateAddr().String(),
			// For checking global permissions
			GlobalPermissionsAddress().ToStateAddr().String())
	}

	encoder := sdk.NewEncoder(priv, sdk.TransactionParams{
		FamilyName:      FAMILY_NAME,
		FamilyVersion:   FAMILY_VERSION,
		PayloadEncoding: ENCODING,
		Inputs:          addresses,
		Outputs:         addresses,
	})

	transaction := &SethTransaction{
		TransactionType: SethTransaction_MESSAGE_CALL,
		MessageCall: &MessageCallTxn{
			Nonce:    nonce,
			GasLimit: gas,
			Data:     data,
			To:       toAddr.Bytes(),
		},
	}

	body, err := c.sendTxn(transaction, encoder, wait)
	if err != nil {
		return nil, err
	}
	logger.Debug(body)

	// In the future, this will return EVM output from the transaction
	return []byte{}, nil
}

// SetPermissions updates the permissions of the account at the given address
// using the account with the given private key.
func (c *Client) SetPermissions(priv, to []byte, permissions *EvmPermissions, nonce uint64, wait int) error {
	if permissions == nil {
		return fmt.Errorf("Permissions must not be nil when setting permissions")
	}
	moderatorAddr, err := PrivToEvmAddr(priv)
	if err != nil {
		return err
	}

	toAddr, err := NewEvmAddrFromBytes(to)
	if err != nil {
		return err
	}

	addresses := []string{
		moderatorAddr.ToStateAddr().String(),
		toAddr.ToStateAddr().String(),
		// For checking global permissions
		GlobalPermissionsAddress().ToStateAddr().String(),
	}

	encoder := sdk.NewEncoder(priv, sdk.TransactionParams{
		FamilyName:      FAMILY_NAME,
		FamilyVersion:   FAMILY_VERSION,
		PayloadEncoding: ENCODING,
		Inputs:          addresses,
		Outputs:         addresses,
	})

	transaction := &SethTransaction{
		TransactionType: SethTransaction_SET_PERMISSIONS,
		SetPermissions: &SetPermissionsTxn{
			To:          toAddr.Bytes(),
			Permissions: permissions,
			Nonce:       nonce,
		},
	}

	body, err := c.sendTxn(transaction, encoder, wait)
	if err != nil {
		return err
	}
	logger.Debug(body)

	return nil
}

func (c *Client) sendTxn(transaction *SethTransaction, encoder *sdk.Encoder, wait int) (*RespBody, error) {
	payload, err := proto.Marshal(transaction)
	if err != nil {
		return nil, fmt.Errorf("Couldn't serialize transaction: %v", err)
	}

	txn := encoder.NewTransaction(payload, sdk.TransactionParams{})
	batch := encoder.NewBatch([]*sdk.Transaction{txn})
	b := sdk.SerializeBatches([]*sdk.Batch{batch})

	buf := bytes.NewReader(b)

	url := c.Url + "/batches"
	if wait > 0 {
		url += fmt.Sprintf("?wait=%v", wait)
	}

	resp, err := http.Post(url, "application/octet-stream", buf)
	if err != nil {
		return nil, fmt.Errorf("Couldn't send transaction: %v", err)
	}

	body, err := ParseRespBody(resp)
	if err != nil {
		return nil, err
	}

	if body.Data != nil {
		data := body.Data.([]interface{})
		status_map := data[0].(map[string]interface{})
		status := status_map["status"].(string)

		if status == "PENDING" {
			return nil, fmt.Errorf("Transaction was submitted, but client timed out before it was committed.")
		}

		if status == "INVALID" {
			return nil, fmt.Errorf("Invalid transaction.")
		}

		if status == "UNKNOWN" {
			return nil, fmt.Errorf("Something went wrong. Try resubmitting the transaction.")
		}
	}

	if body.Error.Code != 0 {
		return nil, &body.Error
	}

	return body, nil
}
