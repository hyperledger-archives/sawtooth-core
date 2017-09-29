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

type ShowEvents struct {
	Positional struct {
		TransactionID string `positional-arg-name:"txn-id" description:"Transaction ID of event list to show"`
	} `positional-args:"true" required:"true"`
}

func (args *ShowEvents) Name() string {
	return "events"
}

func (args *ShowEvents) Register(parent *flags.Command) error {
	_, err := parent.AddCommand(args.Name(), "Show events associated with a given transaction ID", "", args)
	return err
}

func (args *ShowEvents) Run(config *Config) (err error) {
	client := client.New(config.Url)

	clientResult, err := client.GetEvents(args.Positional.TransactionID)
	if err != nil {
		return err
	}
	if len(clientResult.Events) == 0 {
		fmt.Println("No events to show")
	} else {
		events, err := clientResult.MarshalJSON()
		if err != nil {
			return fmt.Errorf("Error displaying events: %s", err.Error())
		}
		fmt.Println("Events: ", string(events))
	}
	return nil
}
