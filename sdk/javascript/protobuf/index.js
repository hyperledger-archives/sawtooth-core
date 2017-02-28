/**
 * Copyright 2016 Intel Corporation
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

'use strict'

const protobuf = require('protobufjs')

const root = protobuf.Root.fromJSON(require('./protobuf_bundle.json'))

const TpRegisterResponse = root.lookup('TpRegisterResponse')
TpRegisterResponse.Status = TpRegisterResponse.nested.Status.values

const TpProcessResponse = root.lookup('TpProcessResponse')
TpProcessResponse.Status = TpProcessResponse.nested.Status.values

const Message = root.lookup('Message')
Message.MessageType = Message.nested.MessageType.values

module.exports = {
  //
  // Validator messages
  Message,

  //
  // processor
  TpRegisterRequest:
    root.lookup('TpRegisterRequest'),

  TpRegisterResponse,

  TpProcessRequest:
    root.lookup('TpProcessRequest'),

  TpProcessResponse,

  //
  // State
  Entry: root.lookup('Entry'),

  TpStateGetRequest: root.lookup('TpStateGetRequest'),

  TpStateGetResponse: root.lookup('TpStateGetResponse'),

  TpStateSetRequest: root.lookup('TpStateSetRequest'),

  TpStateSetResponse: root.lookup('TpStateSetResponse'),

  //
  // Transaction
  TransactionHeader: root.lookup('TransactionHeader')
}
