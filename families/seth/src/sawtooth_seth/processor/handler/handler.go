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

package handler

import (
	evm "burrow/evm"
	. "burrow/word256"
	"encoding/hex"
	"fmt"
	"github.com/golang/protobuf/proto"
	"sawtooth_sdk/logging"
	"sawtooth_sdk/processor"
	"sawtooth_sdk/protobuf/processor_pb2"
	"sawtooth_sdk/protobuf/transaction_pb2"
	. "sawtooth_seth/common"
	. "sawtooth_seth/protobuf/block_info_pb2"
	. "sawtooth_seth/protobuf/seth_pb2"
)

type HandlerResult struct {
	GasUsed     uint64
	ReturnValue []byte
	NewAccount  *evm.Account
	Error       error
}

type TransactionHandler func(*SethTransaction, *EvmAddr, *SawtoothAppState) HandlerResult

var logger *logging.Logger = logging.Get()

type BurrowEVMHandler struct{}

func NewBurrowEVMHandler() *BurrowEVMHandler {
	return &BurrowEVMHandler{}
}

func (self *BurrowEVMHandler) FamilyName() string {
	return FAMILY_NAME
}

func (self *BurrowEVMHandler) FamilyVersions() []string {
	return []string{FAMILY_VERSION}
}

func (self *BurrowEVMHandler) Namespaces() []string {
	return []string{PREFIX}
}

func (self *BurrowEVMHandler) Apply(request *processor_pb2.TpProcessRequest, context *processor.Context) error {

	// Unpack and validate transaction
	wrapper, err := unpackPayload(request.GetPayload())
	if err != nil {
		return err
	}

	// Unpack and validate header
	header, err := unpackHeader(request)
	if err != nil {
		return err
	}

	// Retrieve the handler for this type of Burrow-EVM transaction
	handler, exists := TxnHandlers[wrapper.GetTransactionType()]
	if !exists {
		return &processor.InvalidTransactionError{Msg: fmt.Sprintf(
			"Unknown transaction type: %v", wrapper.GetTransactionType(),
		)}
	}

	// Construct address of sender. This is the address used by the EVM to
	// access the account.
	public_key, decodeErr := hex.DecodeString(header.GetSignerPublicKey())
	if decodeErr != nil {
		return &processor.InternalError{Msg: fmt.Sprintf(
			"Couldn't decode public key",
		)}
	}
	sender, err := PubToEvmAddr(public_key)
	if err != nil {
		return &processor.InvalidTransactionError{Msg: fmt.Sprintf(
			"Couldn't determine sender from public key: %v", header.GetSignerPublicKey(),
		)}
	}

	// Construct new state manager
	sapps := NewSawtoothAppState(context)

	// Call the handler
	result := handler(wrapper, sender, sapps)
	if result.Error != nil {
		return result.Error
	}

	var contractAddress []byte
	if result.NewAccount != nil {
		contractAddress = result.NewAccount.Address.Bytes()
	}
	receipt := &SethTransactionReceipt{
		ContractAddress: contractAddress,
		GasUsed:         result.GasUsed,
		ReturnValue:     result.ReturnValue,
	}
	bytes, err := proto.Marshal(receipt)
	if err != nil {
		return &processor.InternalError{Msg: fmt.Sprintf(
			"Couldn't marshal receipt: %v", err,
		)}
	}
	err = context.AddReceiptData(bytes)
	if err != nil {
		return &processor.InternalError{Msg: fmt.Sprintf(
			"Couldn't set receipt data: %v", err,
		)}
	}

	return nil
}

// -- utilities --

func callVm(sas *SawtoothAppState, sender, receiver *evm.Account,
	code, input []byte, gas uint64) ([]byte, uint64, error) {
	// Create EVM
	params, err := getParams(sas.mgr.state)
	if err != nil {
		return nil, 0, fmt.Errorf("Block Info Error: %v", err)
	}
	vm := evm.NewVM(sas, *params, Zero256, nil)
	evc := NewSawtoothEventFireable(sas.mgr.state)
	vm.SetFireable(evc)

	// Convert the gas to a signed int to be compatible with the burrow EVM
	startGas := int64(gas)
	endGas := int64(gas)

	if receiver == nil {
		receiver = sender
	}

	output, err := vm.Call(sender, receiver, code, input, 0, &endGas)
	if err != nil {
		return nil, 0, fmt.Errorf("EVM Error: %v", err)
	}
	return output, uint64(startGas - endGas), nil
}

func unpackPayload(payload []byte) (*SethTransaction, error) {
	if payload == nil {
		return nil, &processor.InvalidTransactionError{
			Msg: "Request must contain payload",
		}
	}

	transaction := &SethTransaction{}
	err := proto.Unmarshal(payload, transaction)
	if err != nil {
		return nil, &processor.InvalidTransactionError{
			Msg: "Malformed request payload",
		}
	}

	return transaction, nil
}

func unpackHeader(request *processor_pb2.TpProcessRequest) (*transaction_pb2.TransactionHeader, error) {
	header := request.GetHeader()

	if header.GetSignerPublicKey() == "" {
		return nil, &processor.InvalidTransactionError{Msg: "Public Key not set"}
	}

	return header, nil
}

func getParams(context *processor.Context) (*evm.Params, error) {
	blockInfoConfig, err := getBlockInfoConfig(context)
	if err != nil {
		logger.Debugf(err.Error())
		logger.Debugf(
			"Block info not available. BLOCKHASH, TIMESTAMP, and BLOCKHEIGHT instructions will result in failure")
		return &evm.Params{
			BlockHeight: 0,
			BlockHash:   Zero256,
			BlockTime:   0,
			GasLimit:    GAS_LIMIT,
		}, nil
	}

	blockInfo, err := getBlockInfo(context, int64(blockInfoConfig.GetLatestBlock()))
	if err != nil {
		return nil, fmt.Errorf("Failed to get block info: %v", err.Error())
	}

	hash, err := StringToWord256(blockInfo.GetHeaderSignature())
	if err != nil {
		return nil, fmt.Errorf("Failed to get block info: %v", err.Error())
	}

	return &evm.Params{
		BlockHeight: int64(blockInfo.GetBlockNum()),
		BlockHash:   hash,
		BlockTime:   int64(blockInfo.GetTimestamp()),
		GasLimit:    GAS_LIMIT,
	}, nil
}

func getBlockInfoConfig(context *processor.Context) (*BlockInfoConfig, error) {
	// Retrieve block info config from global state
	entries, err := context.GetState([]string{CONFIG_ADDRESS})
	if err != nil {
		return nil, err
	}
	entryData, exists := entries[CONFIG_ADDRESS]
	if !exists {
		return nil, fmt.Errorf("BlockInfo entry does not exist")
	}

	// Deserialize the entry
	entry := &BlockInfoConfig{}
	err = proto.Unmarshal(entryData, entry)
	if err != nil {
		return nil, err
	}

	return entry, nil
}

func getBlockInfo(context *processor.Context, blockNumber int64) (*BlockInfo, error) {
	// Create block info address
	blockInfoAddr, err := NewBlockInfoAddr(blockNumber)
	if err != nil {
		return nil, fmt.Errorf("Failed to get block info address: %v", err.Error())
	}
	// Retrieve block info from global state
	entries, err := context.GetState([]string{blockInfoAddr.String()})
	if err != nil {
		return nil, err
	}
	entryData, exists := entries[blockInfoAddr.String()]
	if !exists {
		return nil, fmt.Errorf("BlockInfo entry does not exist")
	}

	// Deserialize the entry
	entry := &BlockInfo{}
	err = proto.Unmarshal(entryData, entry)
	if err != nil {
		return nil, err
	}

	return entry, nil
}

func StringToWord256(s string) (Word256, error) {
	bytes, err := hex.DecodeString(s)
	if err != nil {
		return Zero256, fmt.Errorf("Couldn't decode string")
	}
	return RightPadWord256(bytes), nil
}
