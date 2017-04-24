package handler

import (
	"crypto/sha512"
	"encoding/hex"
	"sawtooth_sdk/processor"
	"sawtooth_sdk/protobuf/processor_pb2"
	"strings"
)

type BurrowEVMPayload struct {
	Data []byte
}

type BurrowEVMHandler struct {
	namespace string
}

func NewBurrowEVMHandler(namespace string) *BurrowEVMHandler {
	return &BurrowEVMHandler{
		namespace: namespace,
	}
}

func (self *BurrowEVMHandler) FamilyName() string {
	return "burrow-evm"
}
func (self *BurrowEVMHandler) FamilyVersion() string {
	return "1.0"
}
func (self *BurrowEVMHandler) Encoding() string {
	return "application/cbor"
}
func (self *BurrowEVMHandler) Namespaces() []string {
	return []string{self.namespace}
}

func (self *BurrowEVMHandler) Apply(request *processor_pb2.TpProcessRequest, state *processor.State) error {
	payloadData := request.GetPayload()
	if payloadData == nil {
		return &processor.InvalidTransactionError{"Must contain payload"}
	}

	return nil
}

func Hexdigest(str string) string {
	hash := sha512.New()
	hash.Write([]byte(str))
	hashBytes := hash.Sum(nil)
	return strings.ToLower(hex.EncodeToString(hashBytes))
}
