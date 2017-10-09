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
  "sawtooth_seth/client"
  sdk "sawtooth_sdk/client"
  "burrow/word256"
)

const (
  PRIV      = "5J7bEeWs14sKkz7yVHfVc2FXKfBe6Hb5oNZxxTKqKZCgjbDTuUj"
  INIT      = "6060604052341561000f57600080fd5b5b6101c88061001f6000396000f300606060405263ffffffff7c01000000000000000000000000000000000000000000000000000000006000350416631ab06ee5811461005e578063812600df146100795780639507d39a14610091578063c20efb90146100b9575b600080fd5b341561006957600080fd5b6100776004356024356100d1565b005b341561008457600080fd5b610077600435610154565b005b341561009c57600080fd5b6100a760043561016d565b60405190815260200160405180910390f35b34156100c457600080fd5b610077600435610182565b005b6000828152602081905260408082208390557fe8f107f31575696188a1b65709adae13d3a3e981a87f6e692d86ff73ca83af7f91339136905173ffffffffffffffffffffffffffffffffffffffff8416815260406020820181815290820183905260608201848480828437820191505094505050505060405180910390a15b5050565b6000818152602081905260409020805460010190555b50565b6000818152602081905260409020545b919050565b600081815260208190526040902080546000190190555b505600a165627a7a723058208554d6e53c1257ef3eeaab8ff827bb77491bac3e6a8b7d895fbdad674e5646650029"
  SET_0_42  = "1ab06ee50000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000002a"
  SET_19_84 = "1ab06ee500000000000000000000000000000000000000000000000000000000000000130000000000000000000000000000000000000000000000000000000000000054"
  INC_19    = "812600df0000000000000000000000000000000000000000000000000000000000000013"
  DEC_0     = "c20efb900000000000000000000000000000000000000000000000000000000000000000"
  GET_0     = "9507d39a0000000000000000000000000000000000000000000000000000000000000000"
  WAIT      = 300
)

func TestIntkey(t *testing.T) {
  client := client.New("http://rest-api:8080")
  priv, _ := sdk.WifToPriv(PRIV)
  init, _ := hex.DecodeString(INIT)
  nonce := uint64(0)

  // Create the EOA
  _, err := client.CreateExternalAccount(priv, nil, nil, 0, WAIT)
  if err != nil {
    t.Error(err.Error())
  }
  nonce += 1

  // Create the Contract
  createContractResult, err := client.CreateContractAccount(priv, init, nil, nonce, 1000, WAIT)
  if err != nil {
   t.Error(err.Error())
  }
  nonce += 1

  // Test event receipt
  cmd, _ := hex.DecodeString(SET_0_42)
  callSetResult, err := client.MessageCall(priv, createContractResult.Address, cmd, nonce, 1000, 300, false)

  if callSetResult.Events[0].Attributes[0].Key != "address" {
    t.Errorf("Event was not created")
  }
  nonce += 1

  cmds := []string{
    SET_19_84,
    INC_19,
    DEC_0,
  }

  for _, c := range cmds {
    cmd, _ := hex.DecodeString(c)
    _, err = client.MessageCall(priv, createContractResult.Address, cmd, nonce, 1000, WAIT, false)
    if err != nil {
      t.Error(err.Error())
    }
    nonce += 1
  }

  entry, err := client.Get(createContractResult.Address)
  if err != nil {
    t.Error(err.Error())
  }

  if len(entry.Storage) != 2 {
    t.Errorf("Storage should have 2 keys, but has %v", len(entry.Storage))
  }

  keys := []string{
    "ad3228b676f7d3cd4284a5443f17f1962b36e491b30a40b2405849e597ba5fb5",
    "50a82f9cbcdfaca82fe46b4a494d325ee6dc33d1fa55b218ab142e6cc2c8a58b",
  }
  vals := []string{
    "0000000000000000000000000000000000000000000000000000000000000029",
    "0000000000000000000000000000000000000000000000000000000000000055",
  }
  for i, pair := range entry.Storage {
    key := hex.EncodeToString(pair.GetKey())
    val := hex.EncodeToString(pair.GetValue())
    if key != keys[i] {
      t.Errorf("Unexpected key in storage: %v", key)
    }
    if val != vals[i] {
      t.Errorf("Key has unexpected value: %v = %v", key, val)
    }
  }

  // Get the value stored at key 0
  cmd, _ = hex.DecodeString(GET_0)
  callGetResult, err := client.MessageCall(priv, createContractResult.Address, cmd, nonce, 1000, 300, false)
  if err != nil {
    t.Fatal(err)
  }
  value := word256.Uint64FromWord256(word256.RightPadWord256(callGetResult.ReturnValue))
  if value != 41 {
    t.Fatalf("Contract returned incorrect value: %v", value)
  }
}
