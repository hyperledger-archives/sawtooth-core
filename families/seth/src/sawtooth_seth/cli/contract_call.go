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
	"sawtooth_seth/client"
	"strconv"
)

type ContractCall struct {
	Positional struct {
		Alias   string `positional-arg-name:"alias" required:"true" description:"Alias of the imported key associated with the contract to be created"`
		Address string `positional-arg-name:"address" description:"Address of contract to call"`
		Data    string `positional-arg-name:"data" required:"true" description:"Input data to pass to contract when called; must conform to contract ABI"`
	} `positional-args:"true"`
	Gas      uint64 `short:"g" long:"gas" description:"Gas limit for contract creation" default:"90000"`
	Nonce    string `short:"n" long:"nonce" description:"Current nonce of moderator account"`
	Wait     int    `short:"w" long:"wait" description:"Number of seconds Seth client will wait for transaction to be committed; if flag passed, default is 60 seconds; if no flag passed, do not wait" optional:"true" optional-value:"60"`
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

	priv, err := LoadKey(args.Positional.Alias)
	if err != nil {
		return err
	}

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

	var nonce uint64
	if args.Nonce == "" {
		nonce, err = client.LookupAccountNonce(priv)
		if err != nil {
			return err
		}
	} else {
		nonce, err = strconv.ParseUint(args.Nonce, 10, 64)
		if err != nil {
			return fmt.Errorf("Invalid nonce `%v`: ", args.Nonce, err)
		}
	}

	clientResult, err := client.MessageCall(priv, addr, data, nonce, args.Gas, args.Wait, args.Chaining)
	if err != nil {
		return fmt.Errorf("Problem submitting account creation transaction: %v", err)
	}

	if args.Wait > 0 {
		fmt.Printf("Contract called\n")
	} else {
		fmt.Printf("Transaction submitted to call contract\n")
	}
	info, err := clientResult.MarshalJSON()
	if err != nil {
		return fmt.Errorf("Error displaying receipt: %s", err.Error())
	}
	fmt.Println("Transaction Receipt: ", string(info))

	return nil
}
