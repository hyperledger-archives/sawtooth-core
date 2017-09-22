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
	. "burrow/evm"
	"encoding/hex"
	"github.com/golang/protobuf/proto"
	"sawtooth_sdk/processor"
	"sawtooth_seth/protobuf/seth_pb2"
)

type SawtoothEventFireable struct {
	context *processor.Context
}

func NewSawtoothEventFireable(context *processor.Context) *SawtoothEventFireable {
	return &SawtoothEventFireable{
		context: context,
	}
}

func (evc *SawtoothEventFireable) FireEvent(eventType string, eventDataLog EventDataLog) error {
	attributes := []processor.Attribute{
		{
			Key:   "address",
			Value: hex.EncodeToString(eventDataLog.Address.Bytes()),
		},
	}

	var topics [][]byte
	for _, topic := range eventDataLog.Topics {
		topics = append(topics, topic.Bytes())
	}

	log := &seth_pb2.EvmLogData{
		Address: eventDataLog.Address.Bytes(),
		Topics:  topics,
		Data:    eventDataLog.Data,
	}
	data, err := proto.Marshal(log)
	if err != nil {
		return err
	}

	evc.context.AddEvent(eventType, attributes, data)
	return nil
}
