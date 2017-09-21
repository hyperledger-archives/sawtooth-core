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
)

type AccountImport struct {
	Force      bool `short:"f" long:"force" description:"Overwrite key with the same alias if it exists"`
	Positional struct {
		KeyFile string `positional-arg-name:"key-file" required:"true" description:"Path to the file that contains the private key to import"`
		Alias   string `positional-arg-name:"alias" required:"true" description:"Alias to assign the private key"`
	} `positional-args:"true"`
}

func (args *AccountImport) Name() string {
	return "import"
}
func (args *AccountImport) Register(parent *flags.Command) error {
	_, err := parent.AddCommand(
		args.Name(), "Import the private and create an alias for later reference",
		"", args,
	)
	if err != nil {
		return err
	}
	return nil
}
func (args *AccountImport) Run(*Config) error {
	keyFilePath := args.Positional.KeyFile
	alias := args.Positional.Alias
	if !pathExists(keyFilePath) {
		return fmt.Errorf("File does not exist %v", keyFilePath)
	}

	buf, err := ioutil.ReadFile(keyFilePath)
	if err != nil {
		return fmt.Errorf("Couldn't load key from file %v: %v", keyFilePath, err)
	}

	if match, _ := path.Match("*.pem", keyFilePath); match {
		err = SaveKey(alias, string(buf), "pem", args.Force)
	} else {
		err = SaveKey(alias, string(buf), "", args.Force)
	}
	if err != nil {
		return fmt.Errorf("Failed to import key: %v", err)
	}

	fmt.Printf("Key at %v imported with alias %v\n", keyFilePath, alias)
	return nil
}
