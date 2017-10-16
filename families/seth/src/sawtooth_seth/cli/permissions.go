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
	"os"
	. "sawtooth_seth/protobuf/seth_pb2"
	"strings"
)

type Permissions struct {
	Subs []Command      `no-flag:"true"`
	Cmd  *flags.Command `no-flag:"true"`
}

func (args *Permissions) Name() string {
	return "permissions"
}

func (args *Permissions) Register(parent *flags.Command) error {
	help := `Permissions can be set for individual EVM accounts. If a permission is not set, account permissions default to those set at the global permissions address. If no permissions are set at the global permissions address, all permissions are allowed.

Supported permissions are:
* root: Change permissions of accounts
* send: Transfer value from an owned account to another account
* call: Execute a deployed contract
* contract: Deploy new contracts from an owned account
* account: Create new externally owned accounts

When a new account is created, its permissions are inherited from the creating account according to the following rules:
- If the account is a new external account, its permissions are inherited from the global permissions address. If no permissions are set at the global permissions address, all permissions are enabled for the new account.
- If the account is a new contract account, its permissions are inherited from the creating account, with the exception of the "root" permission, which is set to deny.

To specify permissions on the command line, use a comma-separated list of "prefixed" permissions from the list above. Permissions must be prefixed with a plus ("+") or minus ("-") to indicated allowed and not allowed respectively. Permissions that are omitted from the list will be left unset and default to those set at the global permissions address.

"all" may be used as a special keyword to refer to all permissions. Duplicates are allowed and items that come later in the list override earlier items.

Examples:

-all,+contract,+call      Disable all permissions except contract creation or calling
+account,+send,-contract  Enable account creation and sending value; Disable contract creation
+all,-root                Enable all permissions except setting permissions`

	var err error
	args.Cmd, err = parent.AddCommand(
		args.Name(), "Manage permissions of accounts", help, args)

	// Add sub-commands
	args.Subs = []Command{
		&PermissionsSet{},
	}
	for _, sub := range args.Subs {
		err := sub.Register(args.Cmd)
		if err != nil {
			logger.Errorf("Couldn't register command %v: %v", sub.Name(), err)
			os.Exit(1)
		}
	}

	return err
}

func (args *Permissions) Run(config *Config) error {
	name := args.Cmd.Active.Name
	for _, sub := range args.Subs {
		if sub.Name() == name {
			err := sub.Run(config)
			if err != nil {
				fmt.Printf("Error: %v\n", err)
				os.Exit(1)
			}
			return nil
		}
	}
	return nil
}

func ParsePermissions(permstr string) (*EvmPermissions, error) {
	perms := &EvmPermissions{}

	for _, ps := range strings.Split(permstr, ",") {
		var (
			bit  bool
			perm uint64
		)
		switch string(ps[0]) {
		case "-":
			bit = false
		case "+":
			bit = true
		default:
			return nil, fmt.Errorf("Prefix not set or invalid: %v", ps)
		}

		switch ps[1:] {
		case "all":
			perm = 1 | 2 | 4 | 8 | 16
		case "root":
			perm = 1
		case "send":
			perm = 2
		case "call":
			perm = 4
		case "contract":
			perm = 8
		case "account":
			perm = 16
		default:
			return nil, fmt.Errorf("Invalid permission: %v", ps)
		}

		if bit {
			perms.Perms |= perm
		} else {
			perms.Perms &= ^perm
		}
		perms.SetBit |= perm
	}
	return perms, nil
}

func SerializePermissions(perms *EvmPermissions) string {
	output := ""
	for i := uint64(1); i <= 16; i <<= 1 {
		var enabled, perm string
		if perms.SetBit&i > 0 {
			if perms.Perms&i > 0 {
				enabled = "+"
			} else {
				enabled = "-"
			}
		}
		switch i {
		case 1:
			perm = "root"
		case 2:
			perm = "send"
		case 4:
			perm = "call"
		case 8:
			perm = "contract"
		case 16:
			perm = "account"
		}
		output += enabled + perm + ","
	}

	return output[:len(output)-1]
}
