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
	. "sawtooth_burrow_evm/protobuf/evm_pb2"
	sdk "sawtooth_sdk/client"
	"sawtooth_sdk/logging"
)

var logger *logging.Logger = logging.Get()

const (
	FAMILY_NAME    = "burrow-evm"
	FAMILY_VERSION = "1.0"
	ENCODING       = "application/protobuf"
	PREFIX         = "a84eda"
)

type Client struct {
	Url string
}

func New(url string) *Client {
	return &Client{
		Url: url,
	}
}

func (c *Client) Load(priv, init []byte, gas uint64) (*RespBody, error) {
	address, err := PrivToAddr(priv)
	if err != nil {
		return nil, err
	}

	encoder := sdk.NewEncoder(priv, sdk.TransactionParams{
		FamilyName:      FAMILY_NAME,
		FamilyVersion:   FAMILY_VERSION,
		PayloadEncoding: ENCODING,
		Inputs:          []string{address},
		Outputs:         []string{address},
	})

	transaction := &EvmTransaction{
		GasLimit: gas,
		Init:     init,
	}

	payload, err := proto.Marshal(transaction)
	if err != nil {
		return nil, fmt.Errorf("Couldn't serialize transaction: %v", err)
	}

	txn := encoder.NewTransaction(payload, sdk.TransactionParams{})
	batch := encoder.NewBatch([]*sdk.Transaction{txn})
	b := sdk.SerializeBatches([]*sdk.Batch{batch})

	buf := bytes.NewReader(b)

	resp, err := http.Post(
		c.Url+"/batches", "application/octet-stream", buf,
	)

	if err != nil {
		return nil, fmt.Errorf("Couldn't send transaction: %v", err)
	}

	return ParseRespBody(resp)
}

func (c *Client) Exec(priv, to, data []byte, gas uint64) (*RespBody, error) {
	fromAddr, err := PrivToAddr(priv)
	if err != nil {
		return nil, err
	}

	toAddr, err := VmAddrToAddr(to)
	if err != nil {
		return nil, err
	}

	encoder := sdk.NewEncoder(priv, sdk.TransactionParams{
		FamilyName:      FAMILY_NAME,
		FamilyVersion:   FAMILY_VERSION,
		PayloadEncoding: ENCODING,
		Inputs:          []string{fromAddr, toAddr},
		Outputs:         []string{fromAddr, toAddr},
	})

	transaction := &EvmTransaction{
		GasLimit: gas,
		Data:     data,
		To:       to,
	}

	payload, err := proto.Marshal(transaction)
	if err != nil {
		return nil, fmt.Errorf("Couldn't serialize transaction: %v", err)
	}

	txn := encoder.NewTransaction(payload, sdk.TransactionParams{})
	batch := encoder.NewBatch([]*sdk.Transaction{txn})
	b := sdk.SerializeBatches([]*sdk.Batch{batch})

	buf := bytes.NewReader(b)

	resp, err := http.Post(
		c.Url+"/batches", "application/octet-stream", buf,
	)
	if err != nil {
		return nil, fmt.Errorf("Couldn't send transaction: %v", err)
	}

	return ParseRespBody(resp)
}

func (c *Client) GetEntry(id []byte, idType string) (*EvmEntry, error) {
	var (
		address string
		err     error
	)
	switch idType {
	case "private":
		address, err = PrivToAddr(id)

	case "public":
		address, err = PubToAddr(id)

	case "address":
		address, err = VmAddrToAddr(id)

	default:
		return nil, fmt.Errorf(
			"Unknown ID type: %v, must be in {private, public, address}", idType,
		)
	}

	if err != nil {
		return nil, err
	}

	resp, err := http.Get(c.Url + "/state/" + address)
	if err != nil {
		return nil, err
	}

	body, err := ParseRespBody(resp)
	if err != nil {
		return nil, err
	}

	buf, err := base64.StdEncoding.DecodeString(body.Data)
	if err != nil {
		return nil, err
	}

	entry := &EvmEntry{}
	err = proto.Unmarshal(buf, entry)
	if err != nil {
		return nil, err
	}

	return entry, nil
}
