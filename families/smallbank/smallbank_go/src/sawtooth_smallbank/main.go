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
	flags "github.com/jessevdk/go-flags"
	"os"
	"sawtooth_sdk/logging"
	"sawtooth_sdk/processor"
	smallbank "sawtooth_smallbank/handler"
	"syscall"
)

var opts struct {
	Verbose []bool `short:"v" long:"verbose" description:"Increase verbosity"`
	Args    struct {
		Endpoint string
	} `positional-args:"yes"`
}

func main() {
	parser := flags.NewParser(&opts, flags.Default)

	_, err := parser.Parse()
	if err != nil {
		if flagsErr, ok := err.(*flags.Error); ok && flagsErr.Type == flags.ErrHelp {
			os.Exit(0)
		} else {
			os.Exit(2)
		}
	}

	endpoint := "tcp://localhost:4004"
	if opts.Args.Endpoint != "" {
		endpoint = opts.Args.Endpoint
	}

	var loggingLevel int
	switch len(opts.Verbose) {
	case 0:
		loggingLevel = logging.WARN
	case 1:
		loggingLevel = logging.INFO
	default:
		loggingLevel = logging.DEBUG
	}

	logger := logging.Get()
	logger.SetLevel(loggingLevel)

	logger.Debugf("command line arguments: %v", os.Args)
	logger.Debugf("verbose = %v\n", len(opts.Verbose))
	logger.Debugf("endpoint = %v\n", endpoint)

	handler := &smallbank.SmallbankHandler{}
	processor := processor.NewTransactionProcessor(endpoint)
	processor.AddHandler(handler)
	processor.ShutdownOnSignal(syscall.SIGINT, syscall.SIGTERM)
	err = processor.Start()
	if err != nil {
		logger.Error("Processor stopped: ", err)
	}
}
