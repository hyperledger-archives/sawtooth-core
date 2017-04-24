// Package processor provides a high-level generic transaction processor that
// any number of handlers can be added to.
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
//     validatorEndpoint := "tcp://localhost:40000"
//     myHandler := NewMyHandler()
//     processor := NewTransactionProcessor(validatorEndpoint)
//     processor.AddHandler(myHandler)
//     processor.Start()
//
// The FamilyName(), FamilyVersion(), Encoding(), and Namespaces() methods are
// used by the processor to route processing requests to the handler.
type TransactionHandler interface {
	// FamilyName should return the name of the transaction family that this
	// handler can process. Eg., "intkey"
	FamilyName() string

	// FamilyVersion should return the version of the transaction family that
	// this handler can process. Eg., "1.0"
	FamilyVersion() string

	// Encoding should return the encoding that this handler can interpret.
	// Eg., "application/cbor"
	Encoding() string

	// Namespaces should return a slice containing all the handler's
	// namespaces. Eg., []string{"abcdef"}
	Namespaces() []string

	// Apply is the single method where all the business logic for a
	// transaction family is defined. The method will be called by the
	// transaction processor upon receiving a TpProcessRequest that the handler
	// understands and will pass in the TpProcessRequest and an initialized
	// instance of the State type.
	Apply(*processor_pb2.TpProcessRequest, *State) error
}
