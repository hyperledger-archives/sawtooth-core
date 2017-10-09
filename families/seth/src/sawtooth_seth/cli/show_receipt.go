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
)

type ShowReceipt struct {
	Positional struct {
		TransactionID string `positional-arg-name:"txn-id" description:"Transaction ID of receipt to show"`
	} `positional-args:"true" required:"true"`
}

func (args *ShowReceipt) Name() string {
	return "receipt"
}

func (args *ShowReceipt) Register(parent *flags.Command) error {
	_, err := parent.AddCommand(args.Name(), "Show receipt associated with a given transaction ID", "", args)
	return err
}

func (args *ShowReceipt) Run(config *Config) (err error) {
	client := client.New(config.Url)

	clientResult, err := client.GetSethReceipt(args.Positional.TransactionID)
	if err != nil {
		return err
	}

	receipt, err := clientResult.MarshalJSON()
	if err != nil {
		return err
	}
	fmt.Println("Seth Transaction Receipt: ", string(receipt))

	return nil
}
