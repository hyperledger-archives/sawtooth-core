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
	"sawtooth_sdk/logging"
)

var logger *logging.Logger = logging.Get()

// All subcommands implement this interface
type Command interface {
	Register(*flags.Command) error
	Name() string
	Run(*Config) error
}

// Opts to the main command
type MainOpts struct {
	Verbose []bool `short:"v" long:"verbose" description:"Set the log level"`
}

func main() {
	var opts MainOpts

	// Create top-level parser
	parser := flags.NewParser(&opts, flags.Default)
	parser.Command.Name = "seth"

	// Add sub-commands
	commands := []Command{
		&Account{},
		&Contract{},
		&Show{},
		&Init{},
		&Permissions{},
	}
	for _, cmd := range commands {
		err := cmd.Register(parser.Command)
		if err != nil {
			logger.Errorf("Couldn't register command %v: %v", cmd.Name(), err)
			os.Exit(1)
		}
	}

	// Parse the args
	remaining, err := parser.Parse()
	if e, ok := err.(*flags.Error); ok {
		if e.Type == flags.ErrHelp {
			return
		} else {
			os.Exit(1)
		}
	}

	if len(remaining) > 0 {
		fmt.Printf("Error: Unrecognized arguments passed: %v\n", remaining)
		os.Exit(2)
	}

	switch len(opts.Verbose) {
	case 2:
		logger.SetLevel(logging.DEBUG)
	case 1:
		logger.SetLevel(logging.INFO)
	default:
		logger.SetLevel(logging.WARN)
	}

	// If a sub-command was passed, run it
	if parser.Command.Active == nil {
		os.Exit(2)
	}

	config, err := LoadConfig()
	if err != nil {
		fmt.Println("Error: Failed to load config: %v", err)
		return
	}

	name := parser.Command.Active.Name
	for _, cmd := range commands {
		if cmd.Name() == name {
			err := cmd.Run(config)
			if err != nil {
				fmt.Printf("Error: %v\n", err)
				os.Exit(1)
			}
			return
		}
	}

	fmt.Println("Error: Command not found: %v", name)
}
