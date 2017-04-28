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
	"os"
	intkey "sawtooth_intkey/handler"
	"sawtooth_sdk/logging"
	"sawtooth_sdk/processor"
)

func main() {
	endpoint := "tcp://localhost:40000"
	if len(os.Args) > 1 {
		// Overwrite the default endpoint if specified
		endpoint = os.Args[1]
	}

	logger := logging.Get()
	logger.SetLevel(logging.INFO)

	prefix := intkey.Hexdigest("intkey")[:6]
	handler := intkey.NewIntkeyHandler(prefix)
	processor := processor.NewTransactionProcessor(endpoint)
	processor.AddHandler(handler)
	processor.Start()
}
