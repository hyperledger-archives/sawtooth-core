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
	"encoding/hex"
	"fmt"
	"github.com/jessevdk/go-flags"
	sdk "sawtooth_sdk/client"
	"sawtooth_seth/client"
)

type ContractCall struct {
	Positional struct {
		Alias   string `positional-arg-name:"alias" required:"true" description:"Alias of the imported key associated with the contract to be created"`
		Address string `positional-arg-name:"address" description:"Address of contract to call"`
		Data    string `positional-arg-name:"data" required:"true" description:"Input data to pass to contract when called; must conform to contract ABI"`
	} `positional-args:"true"`
	Gas      uint64 `short:"g" long:"gas" description:"Gas limit for contract creation" default:"0"`
	Nonce    uint64 `short:"n" long:"nonce" description:"Current nonce of moderator account" default:"0"`
	Wait     int    `short:"w" long:"wait" description:"Number of seconds Seth client will wait for transaction to be committed" default:"0" optional:"true" optional-value:"60"`
	Chaining bool   `short:"c" long:"chaining-enabled" description:"If true, enables contract chaining" defalt:"False"`
}

func (args *ContractCall) Name() string {
	return "call"
}

func (args *ContractCall) Register(parent *flags.Command) error {
	_, err := parent.AddCommand(
		args.Name(), "Execute a deployed contract account",
		"", args,
	)
	if err != nil {
		return err
	}
	return nil
}

func (args *ContractCall) Run(config *Config) error {
	client := client.New(config.Url)

	key, err := LoadKey(args.Positional.Alias)
	if err != nil {
		return fmt.Errorf("Couldn't load key from alias: %v", err)
	}
	priv, _ := sdk.WifToPriv(key)

	data, err := hex.DecodeString(args.Positional.Data)
	if err != nil {
		return fmt.Errorf("Invalid contract input data: %v", err)
	}

	addr, err := hex.DecodeString(args.Positional.Address)
	if err != nil {
		return fmt.Errorf("Invalid address: %v", err)
	}

	if args.Wait < 0 {
		return fmt.Errorf("Invalid wait specified: %v. Must be a positive integer", args.Wait)
	}

	_, err = client.MessageCall(priv, addr, data, args.Nonce, args.Gas, args.Wait, args.Chaining)
	if err != nil {
		return fmt.Errorf("Problem submitting account creation transaction: %v", err)
	}

	if args.Wait > 0 {
		fmt.Printf(
			"Contract called at %v\n", hex.EncodeToString(addr),
		)
	} else {
		fmt.Printf(
			"Transaction submitted to call contract at %v\n", hex.EncodeToString(addr),
		)
	}

	return nil
}
