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

type Load struct {
	Private string `short:"k" long:"key" required:"true" description:"A hex encoded private key to create the account with. See 'sawtooth keygen' for creation."`
	Init    string `short:"i" long:"init" description:"Hex encoded initialization code to run on account creation."`
	Url     string `short:"U" long:"url" description:"The REST API URL to connect to when sending the transaction." default:"http://127.0.0.1:8080"`
	Gas     uint64 `short:"g" long:"gas" description:"Amount of gas to supply the transaction with." default:"1000"`
	Nonce   uint64 `short:"n" long:"nonce" description:"Nonce to set in the transaction." default:"0"`
}

func (c *Load) Name() string {
	return "load"
}

func (c *Load) Register(p *flags.Parser) error {
	_, err := p.AddCommand("load", "Load a new account into state", "", c)
	return err
}

func (c *Load) Run() error {
	client := client.New(c.Url)

	priv, err := decodeFileOrArg(c.Private)
	if err != nil {
		return err
	}

	init, err := decodeFileOrArg(c.Init)
	if err != nil {
		return err
	}

	response, err := client.Load(priv, init, c.Gas, c.Nonce)
	if err != nil {
		return err
	}

	fmt.Println(response)
	return nil
}
