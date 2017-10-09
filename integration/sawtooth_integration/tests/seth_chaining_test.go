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
 "bytes"
 "testing"
 c "sawtooth_seth/client"
 sdk "sawtooth_sdk/client"
 "encoding/hex"
 "sawtooth_sdk/logging"
)

const (
  PRIV = "5J7bEeWs14sKkz7yVHfVc2FXKfBe6Hb5oNZxxTKqKZCgjbDTuUj"
  INIT_CALLER = "6060604052341561000f57600080fd5b5b6101388061001f6000396000f300606060405263ffffffff7c0100000000000000000000000000000000000000000000000000000000600035041663b41d7af4811461003d575b600080fd5b341561004857600080fd5b61006973ffffffffffffffffffffffffffffffffffffffff6004351661007b565b60405190815260200160405180910390f35b60008173ffffffffffffffffffffffffffffffffffffffff811663c605f76c83604051602001526040518163ffffffff167c0100000000000000000000000000000000000000000000000000000000028152600401602060405180830381600087803b15156100e957600080fd5b6102c65a03f115156100fa57600080fd5b50505060405180519250505b509190505600a165627a7a72305820ac041b383966301cf39e20d02fd65bd09442a888f34952c12ecfe18c0dc7a3cf0029"
  INIT_CALLEE = "6060604052341561000f57600080fd5b5b60af8061001e6000396000f300606060405263ffffffff7c0100000000000000000000000000000000000000000000000000000000600035041663c605f76c8114603c575b600080fd5b3415604657600080fd5b604c605e565b60405190815260200160405180910390f35b7f68656c6c6f776f726c64000000000000000000000000000000000000000000005b905600a165627a7a723058206daedea9007da979c290c268d5ae84c5b4e1b692c31b6f0abd4d5804a169e0650029"
  CALL_HELLO_WORLD = "b41d7af4000000000000000000000000b257af145523371812eb8dfd1b22ddcb18e6a91a"

  WAIT = 300
)

var logger *logging.Logger = logging.Get()

func TestContractChaining(t *testing.T) {
  client := c.New("http://rest-api:8080")
  priv, _ := sdk.WifToPriv(PRIV)
  init_callee, _ := hex.DecodeString(INIT_CALLEE)
  init_caller, _ := hex.DecodeString(INIT_CALLER)
  nonce := uint64(0)

  // Create the EOA
  _, err := client.CreateExternalAccount(priv, nil, nil, 0, WAIT)
  if err != nil {
    t.Error(err.Error())
  }
  nonce += 1

  // Create callee contract
  _, err = client.CreateContractAccount(priv, init_callee, nil, nonce, 1000, WAIT)
  if err != nil {
   t.Error(err.Error())
  }
  nonce += 1

  // Create caller contract
  callerContractResult, err := client.CreateContractAccount(priv, init_caller, nil, nonce, 1000, WAIT)
  if err != nil {
   t.Error(err.Error())
  }
  nonce += 1

  // Call contract
  cmd, _ := hex.DecodeString(CALL_HELLO_WORLD)
  callResult, err := client.MessageCall(priv, callerContractResult.Address, cmd, nonce, 1000, WAIT, true)

  // Convert return value to string
  n := bytes.IndexByte(callResult.ReturnValue, 0)
  value := string(callResult.ReturnValue[:n])

  // Compare value
  if value != "helloworld" {
    t.Fatalf("Incorrect return value: '%s', expected 'helloworld'", value)
  }
}
