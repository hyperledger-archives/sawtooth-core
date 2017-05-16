package handler

import (
	evm "burrow/evm"
	. "burrow/word256"
	"crypto/sha512"
	"encoding/hex"
	"github.com/golang/protobuf/proto"
	"sawtooth_sdk/logging"
	"sawtooth_sdk/processor"
	. "sawtooth_sdk/protobuf/evm_pb2"
	"sawtooth_sdk/protobuf/processor_pb2"
	"strings"
)

var logger *logging.Logger = logging.Get()

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
	return "application/protobuf"
}
func (self *BurrowEVMHandler) Namespaces() []string {
	return []string{self.namespace}
}

func (self *BurrowEVMHandler) Apply(request *processor_pb2.TpProcessRequest, state *processor.State) error {
	requestPayload := request.GetPayload()
	if requestPayload == nil {
		return &processor.InvalidTransactionError{"Request must contain payload"}
	}

	// The process request contains a wrapped payload for the EVM
	evmPayload := &EvmPayload{}
	proto.Unmarshal(requestPayload, evmPayload)

	sas := NewSawtoothAppState(self.namespace, state)

	// Unpack EVM args
	caller := &evm.Account{
		Address: Int64ToWord256(evmPayload.GetCaller()),
	}
	callee := &evm.Account{
		Address: Int64ToWord256(evmPayload.GetCallee()),
	}
	code := evmPayload.GetCode()
	input := evmPayload.GetInput()
	value := evmPayload.GetValue()
	gas := evmPayload.GetGas()

	// Create EVM
	params := evm.Params{
		BlockHeight: 0,
		BlockHash:   Zero256,
		BlockTime:   0,
		GasLimit:    0,
	}
	vm := evm.NewVM(sas, params, Zero256, nil)

	// Run the transaction
	output, err := vm.Call(caller, callee, code, input, value, &gas)
	if err != nil {
		logger.Error("EVM Error: ", err)
	} else {
		logger.Debug("EVM Output: ", output)
	}

	return nil
}

func Hexdigest(str string) string {
	hash := sha512.New()
	hash.Write([]byte(str))
	hashBytes := hash.Sum(nil)
	return strings.ToLower(hex.EncodeToString(hashBytes))
}
