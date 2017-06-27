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

package common

import (
	"burrow/word256"
	"fmt"
	"sawtooth_sdk/client"
)

type StateAddr string

func NewStateAddrFromBytes(b []byte) (StateAddr, error) {
	switch len(b) {
	case EVMADDRLEN:
		b := word256.RightPadBytes(b, 32)
		return StateAddr(PREFIX + client.MustEncode(b)), nil
	case STATEADDRLEN:
		return StateAddr(client.MustEncode(b)), nil
	}

	return "", fmt.Errorf(
		"Malformed address (%v): Length must be %v or %v bytes, not %v",
		b, len(b), EVMADDRLEN, STATEADDRLEN,
	)
}

func NewStateAddrFromString(s string) (sa StateAddr, err error) {
	defer func() {
		if r := recover(); r != nil {
			sa = ""
			err = fmt.Errorf("%v could not be decoded: %v", s, r)
		}
	}()
  return NewStateAddrFromBytes(client.MustDecode(s))
}


func (sa StateAddr) String() string {
	return string(sa)
}

func (sa StateAddr) ToEvmAddr() *EvmAddr {
	ea, err := NewEvmAddrFromString(sa.String())
  if err != nil {
    panic(err.Error())
  }
  return ea
}
