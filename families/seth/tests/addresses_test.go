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

package tests

import (
  "encoding/hex"
  "testing"
  . "sawtooth_seth/common"
)

const (
  PRIV = "b66691acf0f79c52462b833b607674ee3fa97a09928b513792782607101de9fe"
  ADDR0 = "0187d022ae80d1010a7297fae9c35c15555cdcbf"
  ADDR1 = "9e94e37000fd8682acee26e9b4419af4938b2ead"
  ADDR2 = "4adcb4c5cc2d634e1c0e2ea97081f2f80eb0537f"
)

func check(err error) {
  if err != nil {
    panic(err.Error())
  }
}

func TestAddresses(t *testing.T) {
  priv, _ := hex.DecodeString(PRIV)

  // Test from private key bytes, public key bytes, and from bytes
  ea, err := PrivToEvmAddr(priv)
  check(err)
  if ea.String() != ADDR0 {
    t.Errorf("%v != %v", ea, ADDR0)
  }

  // Test from string
  ea, err = NewEvmAddrFromString(ADDR0)
  check(err)
  if ea.String() != ADDR0 {
    t.Errorf("%v != %v", ea, ADDR0)
  }

  _, err = NewEvmAddrFromString("tyza")
  if err == nil {
    t.Error("Error expected, but none returned.")
  }

  ea1 := ea.Derive(1)
  if ea1.String() != ADDR1 {
    t.Errorf("%v != %v", ea1, ADDR1)
  }

  ea2 := ea.Derive(2)
  if ea2.String() != ADDR2 {
    t.Errorf("%v != %v", ea2, ADDR2)
  }

  if ea2.ToStateAddr().ToEvmAddr().String() != ea2.String() {
    t.Errorf("Conversion between StateAddr and EvmAddr failed.")
  }
}
