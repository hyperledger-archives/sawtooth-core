package processor

import (
	"sawtooth_sdk/protobuf/processor_pb2"
)

type TransactionHandler interface {
	FamilyName() string
	FamilyVersion() string
	Encoding() string
	Namespaces() []string
	Apply(*processor_pb2.TpProcessRequest, *State) error
}
