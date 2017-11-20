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

// Package processor defines:
// 1. A TransactionHandler interface to be used to create new transaction
// families.
//
// 2. A high-level, general purpose, multi-threaded TransactionProcessor that
// any number of handlers can be added to.
//
// 3. A Context class used to abstract getting and setting addresses in global
// validator state.
package processor

import (
	"sawtooth_sdk/protobuf/processor_pb2"
)

// TransactionHandler is the interface that defines the business logic for a
// new transaction family. This is the only interface that needs to be
// implemented to create a new transaction family.
//
// To create a transaction processor that uses a new transaction handler:
//
//     validatorEndpoint := "tcp://localhost:4004"
//     myHandler := NewMyHandler()
//     processor := NewTransactionProcessor(validatorEndpoint)
//     processor.AddHandler(myHandler)
//     processor.Start()
//
// The FamilyName(), FamilyVersions(), and Namespaces() methods are
// used by the processor to route processing requests to the handler.
type TransactionHandler interface {
	// FamilyName should return the name of the transaction family that this
	// handler can process, e.g. "intkey"
	FamilyName() string

	// FamilyVersions should return the versions of the transaction
	// family that this handler can process. Eg., ["1.0", "1.5"]
	FamilyVersions() []string

	// Namespaces should return a slice containing all the handler's
	// namespaces, e.g. []string{"abcdef"}
	Namespaces() []string

	// Apply is the single method where all the business logic for a
	// transaction family is defined. The method will be called by the
	// transaction processor upon receiving a TpProcessRequest that the handler
	// understands and will pass in the TpProcessRequest and an initialized
	// instance of the Context type.
	Apply(*processor_pb2.TpProcessRequest, *Context) error
}
