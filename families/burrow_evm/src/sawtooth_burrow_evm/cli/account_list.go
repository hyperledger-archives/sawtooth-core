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
	"io/ioutil"
	"path"
	. "sawtooth_burrow_evm/common"
	sdk "sawtooth_sdk/client"
)

type AccountList struct{}

func (args *AccountList) Name() string {
	return "list"
}
func (args *AccountList) Register(parent *flags.Command) error {
	_, err := parent.AddCommand(
		args.Name(), "List all imported accounts as \"alias: address\"",
		"", args,
	)
	return err
}
func (args *AccountList) Run(*Config) error {
	keyDir := getKeyDir()
	if !pathExists(keyDir) {
		fmt.Println("No accounts have been imported.")
		return nil
	}

	keys, err := ioutil.ReadDir(keyDir)
	if err != nil {
		fmt.Errorf("Couldn't list keys: %v", err)
	}
	for _, keyfile := range keys {
		keyname := keyfile.Name()
		if match, _ := path.Match("*.priv", keyname); match {
			alias := keyname[:len(keyname)-5]
			key, err := LoadKey(alias)
			if err != nil {
				return err
			}
			priv := sdk.WifToPriv(key)
			addr, err := PrivToEvmAddr(priv)
			if err != nil {
				return fmt.Errorf(
					"Failed to derive address from key with alias %v: %v", alias, err,
				)
			}
			fmt.Printf("%v: %v\n", alias, addr)
		}
	}

	return nil
}
