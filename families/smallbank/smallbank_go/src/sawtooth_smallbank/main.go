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
	Connect string `short:"C" long:"connect" description:"The validator component endpoint to" default:"tcp://localhost:4004"`
	Queue   uint   `long:"max-queue-size" description:"Set the maximum queue size before rejecting process requests" default:"100"`
	Threads uint   `long:"worker-thread-count" description:"Set the number of worker threads to use for processing requests in parallel" default:"0"`
}

func main() {
	parser := flags.NewParser(&opts, flags.Default)

	logger := logging.Get()

	_, err := parser.Parse()
	if err != nil {
		if flagsErr, ok := err.(*flags.Error); ok && flagsErr.Type == flags.ErrHelp {
			os.Exit(0)
		} else {
			logger.Error("Failed to parse args: ", err)
			os.Exit(2)
		}
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
	logger.SetLevel(loggingLevel)

	logger.Debugf("command line arguments: %v", os.Args)
	logger.Debugf("verbose = %v\n", len(opts.Verbose))
	logger.Debugf("endpoint = %v\n", opts.Connect)

	handler := &smallbank.SmallbankHandler{}
	processor := processor.NewTransactionProcessor(opts.Connect)
	processor.SetMaxQueueSize(opts.Queue)
	if opts.Threads > 0 {
		processor.SetThreadCount(opts.Threads)
	}
	processor.AddHandler(handler)
	processor.ShutdownOnSignal(syscall.SIGINT, syscall.SIGTERM)
	err = processor.Start()
	if err != nil {
		logger.Error("Processor stopped: ", err)
	}
}
