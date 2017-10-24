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

type PermissionsSet struct {
	Positional struct {
		Moderator string `positional-arg-name:"moderator" required:"true" description:"Alias of key to be used for modifying permissions"`
	} `positional-args:"true"`
	Address     string `short:"a" long:"address" required:"true" description:"Address of account whose permissions are being changed; 'global' may be used to refer to the zero address"`
	Permissions string `short:"p" long:"permissions" required:"true" description:"New permissions for the account"`
	Nonce       string `short:"n" long:"nonce" description:"Current nonce of the moderator account; If not passed, the current value will be retrieved"`
	Wait        int    `short:"w" long:"wait" description:"Number of seconds Seth client will wait for transaction to be committed; If flag passed, default is 60 seconds; If no flag passed, do not wait" optional:"true" optional-value:"60"`
}

func (args *PermissionsSet) Name() string {
	return "set"
}

func (args *PermissionsSet) Register(parent *flags.Command) error {
	_, err := parent.AddCommand(
		args.Name(), "Change the permissions of accounts",
		"See 'seth permissions -h' for more info.", args,
	)
	return err
}

func (args *PermissionsSet) Run(config *Config) error {
	client := client.New(config.Url)
	mod, err := LoadKey(args.Positional.Moderator)
	if err != nil {
		return err
	}

	if args.Address == "global" {
		args.Address = "0000000000000000000000000000000000000000"
	}
	addr, err := hex.DecodeString(args.Address)
	if err != nil {
		return fmt.Errorf("Invalid address: %v", err)
	}

	perms, err := ParsePermissions(args.Permissions)
	if err != nil {
		return fmt.Errorf("Invalid permissions: %v", err)
	}

	if args.Wait < 0 {
		return fmt.Errorf("Invalid wait specified: %v. Must be a positive integer", args.Wait)
	}

	var nonce uint64
	if args.Nonce == "" {
		nonce, err = client.LookupAccountNonce(mod)
		if err != nil {
			return err
		}
	} else {
		nonce, err = strconv.ParseUint(args.Nonce, 10, 64)
		if err != nil {
			return fmt.Errorf("Invalid nonce `%v`: ", args.Nonce, err)
		}
	}

	err = client.SetPermissions(mod, addr, perms, nonce, args.Wait)
	if err != nil {
		return fmt.Errorf("Problem submitting transaction to change permissions: %v", err)
	}

	if args.Wait > 0 {
		fmt.Printf(
			"Permissions changed of %v\n", hex.EncodeToString(addr),
		)
	} else {
		fmt.Printf(
			"Transaction submitted to change permissions of %v\n", hex.EncodeToString(addr),
		)
	}

	return nil
}
