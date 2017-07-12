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
	"sawtooth_burrow_evm/client"
	. "sawtooth_burrow_evm/protobuf/evm_pb2"
	sdk "sawtooth_sdk/client"
)

type ContractCreate struct {
	Positional struct {
		Alias string `positional-arg-name:"alias" required:"true" description:"Alias of the imported key associated with the contract to be created"`
		Init  string `positional-arg-name:"init" required:"true" description:"Initialization code to be executed on deployment"`
	} `positional-args:"true"`
	Permissions string `short:"p" long:"permissions" description:"Permissions for new account; see 'seth permissions -h' for more info"`
	Gas         uint64 `short:"g" long:"gas" description:"Gas limit for contract creation" default:"0"`
	Nonce       uint64 `short:"n" long:"nonce" description:"Current nonce of moderator account" default:"0"`
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

	key, err := LoadKey(args.Positional.Alias)
	if err != nil {
		return fmt.Errorf("Couldn't load key from alias: %v", err)
	}
	priv := sdk.WifToPriv(key)

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

	addr, err := client.CreateContractAccount(priv, init, perms, args.Nonce, args.Gas)
	if err != nil {
		return fmt.Errorf("Problem submitting account creation transaction: %v", err)
	}

	fmt.Printf(
		"Transaction submitted to create contract at %v\n", hex.EncodeToString(addr),
	)

	return nil
}
