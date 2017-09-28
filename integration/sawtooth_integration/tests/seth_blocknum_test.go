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
  "burrow/word256"
  "encoding/base64"
  "encoding/hex"
  "fmt"
  "net/http"
  "github.com/golang/protobuf/proto"
  c "sawtooth_seth/client"
  sdk "sawtooth_sdk/client"
  . "sawtooth_seth/common"
  . "sawtooth_seth/protobuf/block_info_pb2"
  "testing"
)

const (
  WAIT = 300
  PRIV = "5J7bEeWs14sKkz7yVHfVc2FXKfBe6Hb5oNZxxTKqKZCgjbDTuUj"
  INIT_BLOCKNUM = "60606040523415600e57600080fd5b5b60978061001d6000396000f300606060405263ffffffff7c0100000000000000000000000000000000000000000000000000000000600035041663503069628114603c575b600080fd5b3415604657600080fd5b604f6004356061565b60405190815260200160405180910390f35b438190035b9190505600a165627a7a723058207ed44310a155801da888f4f3f9d43dea1eeff7828fad8a48a60f7b4364da57070029" 
  BLOCKNUM_0 = "503069620000000000000000000000000000000000000000000000000000000000000000"
)

// Test getting the block number of the current block
func TestBlockNumber(t *testing.T) {
  client := c.New("http://rest-api:8080")
  priv, _ := sdk.WifToPriv(PRIV)
  init, _ := hex.DecodeString(INIT_BLOCKNUM)
  nonce := uint64(0)

  // Create the EOA
  _, err := client.CreateExternalAccount(priv, nil, nil, 0, WAIT)
  if err != nil {
    t.Error(err.Error())
  }
  nonce += 1

  // Create the Contract
  contractCreateResult, err := client.CreateContractAccount(priv, init, nil, nonce, 1000, WAIT)
  if err != nil {
   t.Error(err.Error())
  }
  nonce += 1

  cmd, _ := hex.DecodeString(BLOCKNUM_0)
  contractCallResult, err := client.MessageCall(priv, contractCreateResult.Address, cmd, nonce, 1000, WAIT, false)
  blockNum := word256.Uint64FromWord256(word256.RightPadWord256(contractCallResult.ReturnValue))

  // Get number of current block from BlockInfo
  blockInfoAddr, err := NewBlockInfoAddr(2);
  if err != nil {
    t.Error(err.Error())
  }
  resp, err := http.Get(fmt.Sprintf("%s/state/%s?wait=%v", client.Url, blockInfoAddr, WAIT))
  if err != nil {
    t.Error(err.Error())
  }
  body, err := c.ParseRespBody(resp)
  if err != nil {
    t.Error(err.Error())
  }
  buf, err := base64.StdEncoding.DecodeString(body.Data.(string))
  if err != nil {
    t.Error(err.Error())
  }
  blockInfo := &BlockInfo{}
  err = proto.Unmarshal(buf, blockInfo)
  expectedBlockNum := blockInfo.GetBlockNum()

  if expectedBlockNum != blockNum {
    t.Fatalf("Incorrect block number: %v, expected: %v", blockNum, expectedBlockNum)
  }
}