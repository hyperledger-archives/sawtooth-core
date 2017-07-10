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

package main

import (
	"fmt"
	"github.com/jessevdk/go-flags"
	"sawtooth_burrow_evm/client"
)

type Exec struct {
	Private string `short:"k" long:"key" required:"true" description:"A hex encoded private key to make the message call with."`
	To      string `short:"t" long:"to" required:"true" description:"A 160 bit hex encoded address of an account to call."`
	Data    string `short:"d" long:"data" description:"Hex encoded data to call the account with."`
	Url     string `short:"U" long:"url" description:"The REST API URL to connect to when sending the transaction." default:"http://127.0.0.1:8080"`
	Gas     uint64 `short:"g" long:"gas" description:"Amount of gas to supply the transaction with." default:"1000"`
	Nonce   uint64 `short:"n" long:"nonce" description:"Nonce to set in the transaction." default:"0"`
}

func (e *Exec) Name() string {
	return "exec"
}

func (e *Exec) Register(p *flags.Parser) error {
	_, err := p.AddCommand("exec", "Call an existing account", "", e)
	return err
}

func (e *Exec) Run() error {
	client := client.New(e.Url)

	priv, err := decodeFileOrArg(e.Private, "wif")
	if err != nil {
		return err
	}
	to, err := decodeFileOrArg(e.To, "hex")
	if err != nil {
		return err
	}
	data, err := decodeFileOrArg(e.Data, "hex")
	if err != nil {
		return err
	}

	response, err := client.Exec(priv, to, data, e.Gas, e.Nonce)
	if err != nil {
		return err
	}

	fmt.Println(response)
	return nil
}
