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
  "time"
  "testing"
  "sawtooth_burrow_evm/client"
  sdk "sawtooth_sdk/client"
)

const (
  PRIV      = "5J7bEeWs14sKkz7yVHfVc2FXKfBe6Hb5oNZxxTKqKZCgjbDTuUj"
  INIT      = "6060604052341561000c57fe5b5b6101c48061001c6000396000f30060606040526000357c0100000000000000000000000000000000000000000000000000000000900463ffffffff1680631ab06ee51461005c578063812600df146100855780639507d39a146100a5578063c20efb90146100d9575bfe5b341561006457fe5b61008360048080359060200190919080359060200190919050506100f9565b005b341561008d57fe5b6100a36004808035906020019091905050610116565b005b34156100ad57fe5b6100c36004808035906020019091905050610148565b6040518082815260200191505060405180910390f35b34156100e157fe5b6100f76004808035906020019091905050610166565b005b8060006000848152602001908152602001600020819055505b5050565b600160006000838152602001908152602001600020540160006000838152602001908152602001600020819055505b50565b6000600060008381526020019081526020016000205490505b919050565b600160006000838152602001908152602001600020540360006000838152602001908152602001600020819055505b505600a165627a7a723058203d60fc69e0e52544039deda2b37c9f9ab67fde5fda29b4dea3088495ff7c096c0029"
  SET_0_42  = "1ab06ee50000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000002a"
  SET_19_84 = "1ab06ee500000000000000000000000000000000000000000000000000000000000000130000000000000000000000000000000000000000000000000000000000000054"
  INC_19    = "812600df0000000000000000000000000000000000000000000000000000000000000013"
  DEC_0     = "c20efb900000000000000000000000000000000000000000000000000000000000000000"
)

func TestIntkey(t *testing.T) {
  client := client.New("http://rest-api:8080")
  priv := sdk.WifToPriv(PRIV)
  pub := sdk.GenPubKey(priv)
  init := sdk.MustDecode(INIT)
  nonce := uint64(0)

  // Create the EOA
  _, err := client.Load(priv, nil, 1000, nonce)
  if err != nil {
    t.Error(err.Error())
  }
  nonce += 1
  time.Sleep(time.Second)

  // Create the Contract
  _, err = client.Load(priv, init, 1000, nonce)
  if err != nil {
   t.Error(err.Error())
  }

  to, err := client.Lookup(pub, nonce)
  if err != nil {
    t.Error(err.Error())
  }
  nonce += 1
  time.Sleep(time.Second)

  cmds := []string{
    SET_0_42,
    SET_19_84,
    INC_19,
    DEC_0,
  }

  for _, c := range cmds {
    exec(t, client, priv, to, sdk.MustDecode(c), nonce)
    nonce += 1
  }

    time.Sleep(3 * time.Second)

  entry, err := client.GetEntry(to, "address")
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
    key := sdk.MustEncode(pair.GetKey())
    val := sdk.MustEncode(pair.GetValue())
    if key != keys[i] {
      t.Errorf("Unexpected key in storage: %v", key)
    }
    if val != vals[i] {
      t.Errorf("Key has unexpected value: %v = %v", key, val)
    }
  }

}

func exec(t *testing.T, client *client.Client, priv, to, data []byte, nonce uint64) {
  _, err := client.Exec(priv, to, data, 1000, nonce)
  if err != nil {
    t.Error(err.Error())
  }
}
