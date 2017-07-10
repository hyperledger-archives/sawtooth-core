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
	"burrow/evm/sha3"
	"burrow/word256"
	"fmt"
	"sawtooth_sdk/client"
)

type EvmAddr [EVMADDRLEN]byte

func PrivToEvmAddr(priv []byte) (*EvmAddr, error) {
	if len(priv) != PRIVLEN {
		return nil, fmt.Errorf(
			"Incorrect private key length (%v), should be %v",
			len(priv), PRIVLEN,
		)
	}
	pub := client.GenPubKey(priv)
	return PubToEvmAddr(pub)
}

func PubToEvmAddr(pub []byte) (*EvmAddr, error) {
	if len(pub) != PUBLEN {
		return nil, fmt.Errorf(
			"Incorrect public key length (%v), should be %v",
			len(pub), PUBLEN,
		)
	}

	return NewEvmAddrFromBytes(sha3.Sha3(pub)[:20])
}

func NewEvmAddrFromBytes(b []byte) (*EvmAddr, error) {
	var ea EvmAddr

	switch len(b) {
	case EVMADDRLEN:
		copy(ea[:], b[:EVMADDRLEN])
		return &ea, nil
	case STATEADDRLEN:
		copy(ea[:], b[PREFIXLEN:PREFIXLEN+EVMADDRLEN])
		return &ea, nil
	}

	return nil, fmt.Errorf(
		"Malformed address (%v): Length must be %v or %v bytes, not %v",
		b, len(b), EVMADDRLEN, STATEADDRLEN,
	)
}

func NewEvmAddrFromString(s string) (ea *EvmAddr, err error) {
	defer func() {
		if r := recover(); r != nil {
			ea = nil
			err = fmt.Errorf("%v could not be decoded: %v", s, r)
		}
	}()
	return NewEvmAddrFromBytes(client.MustDecode(s))
}

func (ea *EvmAddr) Derive(nonce uint64) *EvmAddr {
	if nonce == 0 {
		addr, err := NewEvmAddrFromBytes(ea.Bytes())
		if err != nil {
			panic(err.Error())
		}
		return addr
	}
	const BUFLEN = EVMADDRLEN + 8
	buf := make([]byte, BUFLEN)
	copy(buf, ea.Bytes())
	word256.PutUint64BE(buf[EVMADDRLEN:], nonce)

	derived, err := NewEvmAddrFromBytes(sha3.Sha3(buf)[:EVMADDRLEN])
	if err != nil {
		panic(err.Error())
	}
	return derived
}

func (ea *EvmAddr) ToWord256() word256.Word256 {
	return word256.RightPadWord256(ea.Bytes())
}

func (ea *EvmAddr) String() string {
	return client.MustEncode(ea.Bytes())
}

func (ea *EvmAddr) Bytes() []byte {
	return (*ea)[:]
}

func (ea *EvmAddr) ToStateAddr() StateAddr {
	sa, err := NewStateAddrFromBytes(ea.Bytes())
	if err != nil {
		panic(err.Error())
	}
	return sa
}
