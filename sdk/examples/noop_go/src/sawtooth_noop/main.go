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
	"flag"
	noop "sawtooth_noop/handler"
	"sawtooth_sdk/logging"
	"sawtooth_sdk/processor"
	"syscall"
)

func main() {
	v := flag.Bool("v", false, "Info level logging")
	vv := flag.Bool("vv", false, "Debug level logging")
	endpoint := "tcp://localhost:4004"

	flag.Parse()
	args := flag.Args()
	if len(args) > 0 {
		// Overwrite the default endpoint if specified
		endpoint = args[0]
	}

	level := logging.WARN
	if *v {
		level = logging.INFO
	}
	if *vv {
		level = logging.DEBUG
	}

	logger := logging.Get()
	logger.SetLevel(level)

	prefix := noop.Hexdigest("noop")[:6]
	handler := noop.NewNoopHandler(prefix)
	processor := processor.NewTransactionProcessor(endpoint)
	processor.AddHandler(handler)
	processor.ShutdownOnSignal(syscall.SIGINT, syscall.SIGTERM)
	err := processor.Start()
	if err != nil {
		logger.Error("Processor stopped: ", err)
	}
}
