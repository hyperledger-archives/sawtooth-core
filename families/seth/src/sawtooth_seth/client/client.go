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
	"encoding/hex"
	"encoding/json"
	"fmt"
	"github.com/golang/protobuf/proto"
	"net/http"
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

type ClientResult struct {
	TransactionID string  `json:",omitempty"`
	Address       []byte  `json:",omitempty"`
	GasUsed       uint64  `json:",omitempty"`
	ReturnValue   []byte  `json:",omitempty"`
	Events        []Event `json:",omitempty"`
}

// Allows address bytes to be encoded to hex for CLI output
func (r *ClientResult) MarshalJSON() ([]byte, error) {
	type Alias ClientResult
	return json.MarshalIndent(&struct {
		*Alias
		Address     string `json:"Address,omitempty"`
		ReturnValue string `json:"ReturnValue,omitempty"`
	}{
		Alias:       (*Alias)(r),
		Address:     hex.EncodeToString(r.Address),
		ReturnValue: hex.EncodeToString(r.ReturnValue),
	}, "", "  ")
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

func (c *Client) LookupAccountNonce(priv []byte) (uint64, error) {
	addr, err := PrivToEvmAddr(priv)
	if err != nil {
		return 0, fmt.Errorf(
			"Coudn't construct address from private key: %v", err,
		)
	}
	entry, err := c.Get(addr.Bytes())
	if err != nil {
		return 0, fmt.Errorf(
			"Coudn't determine nonce for account with address `%v`: %v",
			addr, err,
		)
	}
	return uint64(entry.Account.Nonce), nil
}

// CreateExternalAccount submits a transaction to create the account with the
// given private key. If moderator is not nil, the account associated with that
// key will be used to create the new account. If perms is not nil, the new
// account is created with the given permissions.
//
// Returns the address of the new account, transaction ID, and receipt.
func (c *Client) CreateExternalAccount(
	priv, moderator []byte, perms *EvmPermissions, nonce uint64, wait int) (*ClientResult, error) {
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
		// For accessing block info
		BLOCK_INFO_PREFIX,
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

	encoder := NewEncoder(sender, TransactionParams{
		FamilyName:    FAMILY_NAME,
		FamilyVersion: FAMILY_VERSION,
		Inputs:        addresses,
		Outputs:       addresses,
	})

	txnID, err := c.sendTxn(transaction, encoder, wait)
	if err != nil {
		return nil, err
	}
	logger.Debug("Tranasaction ID: %s", txnID)

	if wait > 0 {
		receipt, err := c.getTransactionReceipt(txnID)
		if err != nil {
			logger.Debug("Unable to get transaction receipt: %s", err.Error())
		} else {
			sethReceipt, events := c.parseTransactionReceipt(receipt)
			return &ClientResult{
				TransactionID: txnID,
				Address:       newAcctAddr.Bytes(),
				GasUsed:       sethReceipt.GetGasUsed(),
				ReturnValue:   sethReceipt.GetReturnValue(),
				Events:        events,
			}, nil
		}
	}
	return &ClientResult{
		TransactionID: txnID,
		Address:       newAcctAddr.Bytes(),
	}, nil
}

// CreateContractAccount creates a new contract associated with the account
// associated with the given private key. The account is initialized with the
// data in init. If permissions are passed, the account is created with those
// permissions.
//
// Returns the address of the new account, transaction ID, and receipt.
func (c *Client) CreateContractAccount(
	priv []byte, init []byte, perms *EvmPermissions, nonce uint64, gas uint64, wait int) (*ClientResult, error) {
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
		// For accessing block info
		BLOCK_INFO_PREFIX,
	}

	encoder := NewEncoder(priv, TransactionParams{
		FamilyName:    FAMILY_NAME,
		FamilyVersion: FAMILY_VERSION,
		Inputs:        addresses,
		Outputs:       addresses,
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

	txnID, err := c.sendTxn(transaction, encoder, wait)
	if err != nil {
		return nil, err
	}
	logger.Debug(txnID)

	if wait > 0 {
		receipt, err := c.getTransactionReceipt(txnID)
		if err != nil {
			logger.Debug("Unable to get transaction receipt: %s", err.Error())
		} else {
			sethReceipt, events := c.parseTransactionReceipt(receipt)
			return &ClientResult{
				TransactionID: txnID,
				Address:       newAcctAddr.Bytes(),
				GasUsed:       sethReceipt.GetGasUsed(),
				ReturnValue:   sethReceipt.GetReturnValue(),
				Events:        events,
			}, nil
		}
	}
	return &ClientResult{
		TransactionID: txnID,
		Address:       newAcctAddr.Bytes(),
	}, nil
}

// MessageCall sends a message call from the account associated with the given
// private key to the account at the address to. data is used as the input
// to the contract call.
//
// Returns the output from the EVM call.
func (c *Client) MessageCall(
	priv, to, data []byte, nonce uint64, gas uint64, wait int, chaining_enabled bool) (*ClientResult, error) {
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
			GlobalPermissionsAddress().ToStateAddr().String(),
			// For accessing block info
			BLOCK_INFO_PREFIX)
	}

	encoder := NewEncoder(priv, TransactionParams{
		FamilyName:    FAMILY_NAME,
		FamilyVersion: FAMILY_VERSION,
		Inputs:        addresses,
		Outputs:       addresses,
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

	txnID, err := c.sendTxn(transaction, encoder, wait)
	if err != nil {
		return nil, err
	}

	if wait > 0 {
		receipt, err := c.getTransactionReceipt(txnID)
		if err != nil {
			logger.Debug("Unable to get transaction receipt: %s", err.Error())
		} else {
			sethReceipt, events := c.parseTransactionReceipt(receipt)
			return &ClientResult{
				TransactionID: txnID,
				Address:       sethReceipt.GetContractAddress(),
				GasUsed:       sethReceipt.GetGasUsed(),
				ReturnValue:   sethReceipt.GetReturnValue(),
				Events:        events,
			}, nil
		}
	}
	return &ClientResult{
		TransactionID: txnID,
	}, nil
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
		// For accessing block info
		BLOCK_INFO_PREFIX,
	}

	encoder := NewEncoder(priv, TransactionParams{
		FamilyName:    FAMILY_NAME,
		FamilyVersion: FAMILY_VERSION,
		Inputs:        addresses,
		Outputs:       addresses,
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

func (c *Client) sendTxn(transaction *SethTransaction, encoder *Encoder, wait int) (string, error) {
	payload, err := proto.Marshal(transaction)
	if err != nil {
		return "", fmt.Errorf("Couldn't serialize transaction: %v", err)
	}

	txn := encoder.NewTransaction(payload, TransactionParams{})
	batch := encoder.NewBatch([]*Transaction{txn})
	b := SerializeBatches([]*Batch{batch})

	buf := bytes.NewReader(b)

	url := c.Url + "/batches"

	resp, err := http.Post(url, "application/octet-stream", buf)
	if err != nil {
		return "", fmt.Errorf("Couldn't send transaction: %v", err)
	}

	body, err := ParseRespBody(resp)
	if err != nil {
		return "", err
	}

	if body.Link != "" {
		status_url := body.Link
		if wait > 0 {
			status_url += fmt.Sprintf("&wait=%v", wait)
		}
		resp, err := http.Get(status_url)
		if err != nil {
			return "", fmt.Errorf("Couldn't send transaction: %v", err)
		}

		body, err := ParseRespBody(resp)
		if err != nil {
			return "", err
		}

		if body.Data != nil {
			data := body.Data.([]interface{})
			status_map := data[0].(map[string]interface{})
			status := status_map["status"].(string)

			if status == "PENDING" {
				return "", fmt.Errorf("Transaction was submitted, but client timed out before it was committed.")
			}

			if status == "INVALID" {
				return "", fmt.Errorf("Invalid transaction.")
			}

			if status == "UNKNOWN" {
				return "", fmt.Errorf("Something went wrong. Try resubmitting the transaction.")
			}
		}

		if body.Error.Code != 0 {
			return "", &body.Error
		}
	} else {
		return "", fmt.Errorf("No batch status link returned!")
	}

	return txn.HeaderSignature, nil
}

func (c *Client) GetSethReceipt(txnID string) (*ClientResult, error) {
	receipt, err := c.getTransactionReceipt(txnID)
	if err != nil {
		return nil, err
	}
	sethReceipt, _ := c.parseTransactionReceipt(receipt)
	return &ClientResult{
		Address:     sethReceipt.GetContractAddress(),
		GasUsed:     sethReceipt.GetGasUsed(),
		ReturnValue: sethReceipt.GetReturnValue(),
	}, nil
}

func (c *Client) GetEvents(txnID string) (*ClientResult, error) {
	receipt, err := c.getTransactionReceipt(txnID)
	if err != nil {
		return nil, err
	}
	_, events := c.parseTransactionReceipt(receipt)
	return &ClientResult{
		Events: events,
	}, nil
}

func (c *Client) parseTransactionReceipt(receipt *TransactionReceipt) (*SethTransactionReceipt, []Event) {
	sethReceipt := &SethTransactionReceipt{}
	buf, err := base64.StdEncoding.DecodeString(receipt.Data[0])
	if err != nil {
		logger.Debugf("Receipt not available")
		sethReceipt = nil
	}
	sethReceipt = &SethTransactionReceipt{}
	err = proto.Unmarshal(buf, sethReceipt)
	return sethReceipt, receipt.Events
}

func (c *Client) getTransactionReceipt(txnID string) (*TransactionReceipt, error) {
	resp, err := http.Get(c.Url + "/receipts?id=" + txnID)
	if err != nil {
		return nil, err
	}

	body, err := ParseReceiptBody(resp)
	if err != nil {
		return nil, err
	}

	if body.Error.Code != 0 {
		return nil, fmt.Errorf(body.Error.Message)
	}

	return &body.Data[0], nil
}
