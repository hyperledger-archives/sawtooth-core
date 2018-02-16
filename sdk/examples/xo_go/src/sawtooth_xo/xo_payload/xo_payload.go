/**
 * Copyright 2018 Intel Corporation
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

package xo_payload

import (
	"fmt"
	"sawtooth_sdk/processor"
	"strconv"
	"strings"
)

type XoPayload struct {
	Name   string
	Action string
	Space  int
}

func FromBytes(payloadData []byte) (*XoPayload, error) {
	if payloadData == nil {
		return nil, &processor.InvalidTransactionError{Msg: "Must contain payload"}
	}

	parts := strings.Split(string(payloadData), ",")
	if len(parts) != 3 {
		return nil, &processor.InvalidTransactionError{Msg: "Payload is malformed"}
	}

	payload := XoPayload{}
	payload.Name = parts[0]
	payload.Action = parts[1]

	if len(payload.Name) < 1 {
		return nil, &processor.InvalidTransactionError{Msg: "Name is required"}
	}

	if len(payload.Action) < 1 {
		return nil, &processor.InvalidTransactionError{Msg: "Action is required"}
	}

	if payload.Action == "take" {
		space, err := strconv.Atoi(parts[2])
		if err != nil {
			return nil, &processor.InvalidTransactionError{
				Msg: fmt.Sprintf("Invalid Space: '%v'", parts[2])}
		}
		payload.Space = space
	}

	if strings.Contains(payload.Name, "|") {
		return nil, &processor.InvalidTransactionError{
			Msg: fmt.Sprintf("Invalid Name (char '|' not allowed): '%v'", parts[2])}
	}

	return &payload, nil
}
