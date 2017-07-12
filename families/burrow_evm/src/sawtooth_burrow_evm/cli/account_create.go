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

type AccountCreate struct {
	Moderator   string `short:"m" long:"moderator" description:"Alias of another account to be used to create the account"`
	Permissions string `short:"p" long:"permissions" description:"Permissions for new account; see 'seth permissions -h' for more info"`
	Nonce       uint64 `short:"n" long:"nonce" description:"Current nonce of moderator account" default:"0"`
	Positional  struct {
		Alias string `positional-arg-name:"alias" required:"true" description:"Alias of the imported key associated with the account to be created"`
	} `positional-args:"true"`
}

func (args *AccountCreate) Name() string {
	return "create"
}

func (args *AccountCreate) Register(parent *flags.Command) error {
	_, err := parent.AddCommand(
		args.Name(), "Create a new externally owned account",
		"", args,
	)
	if err != nil {
		return err
	}
	return nil
}

func (args *AccountCreate) Run(config *Config) error {
	client := client.New(config.Url)

	key, err := LoadKey(args.Positional.Alias)
	if err != nil {
		return fmt.Errorf("Couldn't load key from alias: %v", err)
	}
	priv := sdk.WifToPriv(key)

	var (
		mod   []byte
		perms *EvmPermissions
	)

	if args.Moderator != "" {
		key, err = LoadKey(args.Moderator)
		if err != nil {
			return fmt.Errorf("Couldn't load moderator from alias: %v", err)
		}
		mod = sdk.WifToPriv(key)
	}

	if args.Permissions != "" {
		perms, err = ParsePermissions(args.Permissions)
		if err != nil {
			return fmt.Errorf("Invalid permissions: %v", err)
		}
	}

	addr, err := client.CreateExternalAccount(priv, mod, perms, args.Nonce)
	if err != nil {
		return fmt.Errorf("Problem submitting account creation transaction: %v", err)
	}

	fmt.Printf(
		"Transaction submitted to create account at %v\n", hex.EncodeToString(addr),
	)

	return nil
}
