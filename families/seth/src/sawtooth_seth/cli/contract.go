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
)

type Contract struct {
	Subs []Command      `no-flag:"true"`
	Cmd  *flags.Command `no-flag:"true"`
}

func (args *Contract) Name() string {
	return "contract"
}

func (args *Contract) Register(parent *flags.Command) error {
	var err error
	args.Cmd, err = parent.AddCommand(args.Name(), "Deploy and execute contracts", "", args)

	// Add sub-commands
	args.Subs = []Command{
		&ContractCreate{},
		&ContractCall{},
		&ContractList{},
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

func (args *Contract) Run(config *Config) error {
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
