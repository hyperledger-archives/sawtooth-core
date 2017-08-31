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

// Lengths are in bytes
const (
	PRIVLEN   = 32
	PUBLEN    = 33
	STATEADDRLEN = 35
	EVMADDRLEN = 20
	PREFIXLEN = 3
	PREFIX    = "a68b06"
	GAS_LIMIT = 1 << 31
	FAMILY_NAME    = "seth"
	FAMILY_VERSION = "1.0"
	ENCODING       = "application/protobuf"
)

func GlobalPermissionsAddress() *EvmAddr {
	addr, _ := NewEvmAddrFromBytes([]byte{
		0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
		0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
	})
	return addr
}
