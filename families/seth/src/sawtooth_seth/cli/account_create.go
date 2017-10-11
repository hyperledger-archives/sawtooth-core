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
	"sawtooth_seth/client"
	. "sawtooth_seth/protobuf/seth_pb2"
	"strconv"
)

type AccountCreate struct {
	Moderator   string `short:"m" long:"moderator" description:"Alias of another account to be used to create the account"`
	Permissions string `short:"p" long:"permissions" description:"Permissions for new account; see 'seth permissions -h' for more info"`
	Nonce       string `short:"n" long:"nonce" description:"Current nonce of the moderator account; if not passed, the current value will be retrieved"`
	Wait        int    `short:"w" long:"wait" description:"Number of seconds Seth client will wait for transaction to be committed, if flag passed, default is 60 seconds; if no flag passed, do not wait" optional:"true" optional-value:"60"`
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

	priv, err := LoadKey(args.Positional.Alias)
	if err != nil {
		return err
	}

	var (
		mod   []byte
		perms *EvmPermissions
	)

	if args.Moderator != "" {
		mod, err = LoadKey(args.Moderator)
		if err != nil {
			return err
		}
	}

	if args.Permissions != "" {
		perms, err = ParsePermissions(args.Permissions)
		if err != nil {
			return fmt.Errorf("Invalid permissions: %v", err)
		}
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

	if args.Wait < 0 {
		return fmt.Errorf("Invalid wait specified: %v. Must be a positive integer", args.Wait)
	}

	clientResult, err := client.CreateExternalAccount(priv, mod, perms, nonce, args.Wait)
	if err != nil {
		return fmt.Errorf("Problem submitting account creation transaction: %v", err)
	}

	if args.Wait > 0 {
		fmt.Printf("Account created\n")
	} else {
		fmt.Printf("Transaction submitted to create account\n")
	}
	info, err := clientResult.MarshalJSON()
	if err != nil {
		return fmt.Errorf("Error displaying receipt: %s", err.Error())
	}
	fmt.Println("Transaction Receipt: ", string(info))

	return nil
}
