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
)

type ShowAccount struct {
	Positional struct {
		Address string `positional-arg-name:"address" description:"Address of account to show"`
	} `positional-args:"true" required:"true"`
}

func (args *ShowAccount) Name() string {
	return "account"
}

func (args *ShowAccount) Register(parent *flags.Command) error {
	_, err := parent.AddCommand(args.Name(), "Show all data associated with a given account", "", args)
	return err
}

func (args *ShowAccount) Run(config *Config) (err error) {
	client := client.New(config.Url)

	addr, err := hex.DecodeString(args.Positional.Address)
	if err != nil {
		return fmt.Errorf("Invalid address: %v", err)
	}

	entry, err := client.Get(addr)
	if err != nil {
		return fmt.Errorf("Couldn't get data at %v: %v", addr, err)
	}

	DisplayEntry(entry)

	return nil
}

func DisplayEntry(entry *EvmEntry) {
	if entry == nil {
		fmt.Println("Nothing at that address")
		return
	}

	acct := entry.GetAccount()

	if len(acct.GetAddress()) == 0 {
		fmt.Println("Account does not exist")
		return
	}

	addr := hex.EncodeToString(acct.GetAddress())
	code := hex.EncodeToString(acct.GetCode())

	fmt.Printf(`
Address: %v
Balance: %v
Code   : %v
Nonce  : %v
`, addr, acct.GetBalance(), code, acct.GetNonce())

	displayPermissions(acct.GetPermissions())
	displayStorage(entry.GetStorage())

}

func displayStorage(stg []*EvmStorage) {
	if stg == nil || len(stg) == 0 {
		fmt.Println("(No Storage Set)\n")
		return
	}

	fmt.Println("Storage:")
	for _, pair := range stg {
		key := hex.EncodeToString(pair.GetKey())
		val := hex.EncodeToString(pair.GetValue())
		fmt.Printf("%v -> %v\n", key, val)
	}
}

func displayPermissions(perms *EvmPermissions) {
	if perms == nil {
		fmt.Println("(No Permissions Set)\n")
	}

	fmt.Printf("Perms  : %v\n", SerializePermissions(perms))
}
