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
)

type Init struct {
	Positional struct {
		Url string `positional-arg-name:"[url]"`
	} `positional-args:"true" required:"true"`
}

func (cmd *Init) Name() string {
	return "init"
}

func (cmd *Init) Register(parent *flags.Command) error {
	_, err := parent.AddCommand(
		"init", "Initialize seth to communicate with the given URL", "", cmd,
	)
	return err
}

func (cmd *Init) Run(*Config) error {
	fmt.Printf("Initializing seth to communicate with %v\n", cmd.Positional.Url)

	err := SaveConfig(&Config{
		Url: cmd.Positional.Url,
	})

	if err != nil {
		return fmt.Errorf("Failed to initialize: %v", err)
	}

	return nil
}
