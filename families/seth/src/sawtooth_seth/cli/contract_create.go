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
	. "sawtooth_seth/protobuf/seth_pb2"
	"strconv"
)

type ContractCreate struct {
	Positional struct {
		Alias string `positional-arg-name:"alias" required:"true" description:"Alias of the imported key associated with the contract to be created"`
		Init  string `positional-arg-name:"init" required:"true" description:"Initialization code to be executed on deployment"`
	} `positional-args:"true"`
	Permissions string `short:"p" long:"permissions" description:"Permissions for new account; see 'seth permissions -h' for more info"`
	Gas         uint64 `short:"g" long:"gas" description:"Gas limit for contract creation" default:"90000"`
	Nonce       string `short:"n" long:"nonce" description:"Current nonce of the moderator account; if not passed, the current value will be retrieved"`
	Wait        int    `short:"w" long:"wait" description:"Number of seconds Seth client will wait for transaction to be committed; if flag passed, default is 60 seconds; if no flag passed, do not wait" optional:"true" optional-value:"60"`
}

func (args *ContractCreate) Name() string {
	return "create"
}

func (args *ContractCreate) Register(parent *flags.Command) error {
	_, err := parent.AddCommand(
		args.Name(), "Deploy a new contract account",
		"", args,
	)
	if err != nil {
		return err
	}
	return nil
}

func (args *ContractCreate) Run(config *Config) error {
	client := client.New(config.Url)

	priv, err := LoadKey(args.Positional.Alias)
	if err != nil {
		return err
	}

	init, err := hex.DecodeString(args.Positional.Init)
	if err != nil {
		return fmt.Errorf("Invalid initialization code: %v", err)
	}

	var perms *EvmPermissions
	if args.Permissions != "" {
		perms, err = ParsePermissions(args.Permissions)
		if err != nil {
			return fmt.Errorf("Invalid permissions: %v", err)
		}
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

	clientResult, err := client.CreateContractAccount(priv, init, perms, nonce, args.Gas, args.Wait)
	if err != nil {
		return fmt.Errorf("Problem submitting account creation transaction: %v", err)
	}

	if args.Wait > 0 {
		fmt.Printf("Contract created\n")
	} else {
		fmt.Printf("Transaction submitted to create contract\n")
	}
	info, err := clientResult.MarshalJSON()
	if err != nil {
		return fmt.Errorf("Error displaying receipt: %s", err.Error())
	}
	fmt.Println("Transaction Receipt: ", string(info))

	return nil
}
