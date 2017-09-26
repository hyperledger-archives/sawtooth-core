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
	. "sawtooth_seth/common"
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

	aliases := make([]string, 0)
	addrs := make([]string, 0)
	for _, keyfile := range keys {
		keyname := keyfile.Name()
		var alias string
		if match, _ := path.Match("*.wif", keyname); match {
			alias = keyname[:len(keyname)-4]
		} else if match, _ := path.Match("*.pem", keyname); match {
			alias = keyname[:len(keyname)-4]
		} else {
			continue
		}
		priv, err := LoadKey(alias)
		if err != nil {
			fmt.Printf("Couldn't load key with alias %v: %v\n", alias, err)
			continue
		}
		addr, err := PrivToEvmAddr(priv)
		if err != nil {
			fmt.Printf(
				"Failed to derive address from key with alias %v: %v\n", alias, err,
			)
			continue
		}
		aliases = append(aliases, alias)
		addrs = append(addrs, addr.String())
	}
	for i, _ := range aliases {
		fmt.Printf("%v: %v\n", aliases[i], addrs[i])
	}

	return nil
}
