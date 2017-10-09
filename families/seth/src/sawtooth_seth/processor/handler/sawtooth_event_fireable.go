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
	"fmt"
	"sawtooth_sdk/processor"
)

type SawtoothEventFireable struct {
	context *processor.Context
}

func NewSawtoothEventFireable(context *processor.Context) *SawtoothEventFireable {
	return &SawtoothEventFireable{
		context: context,
	}
}

func (evc *SawtoothEventFireable) FireEvent(eventID string, eventDataLog EventDataLog) error {
	attributes := []processor.Attribute{
		{
			Key:   "address",
			Value: hex.EncodeToString(eventDataLog.Address.Postfix(20)),
		},
		{
			Key:   "eventID",
			Value: eventID,
		},
	}
	for i, topic := range eventDataLog.Topics {
		attributes = append(attributes, processor.Attribute{
			Key:   fmt.Sprintf("topic%v", i+1),
			Value: hex.EncodeToString(topic.Bytes()),
		})
	}
	evc.context.AddEvent("seth_log_event", attributes, eventDataLog.Data)
	return nil
}
