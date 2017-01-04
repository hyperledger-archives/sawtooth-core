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

const Acknowledgement = root.lookup('Acknowledgement')
Acknowledgement.Status = Acknowledgement.nested.Status.values

const TransactionProcessResponse = root.lookup('TransactionProcessResponse')
TransactionProcessResponse.Status = TransactionProcessResponse.nested.Status.values

module.exports = {
  Message: root.lookup('Message'),

  MessageList: root.lookup('MessageList'),

  //
  // processor
  TransactionProcessorRegisterRequest:
    root.lookup('TransactionProcessorRegisterRequest'),

  Acknowledgement,

  TransactionProcessRequest:
    root.lookup('TransactionProcessRequest'),

  TransactionProcessResponse,

  //
  // State
  Entry: root.lookup('Entry'),

  GetRequest: root.lookup('GetRequest'),

  GetResponse: root.lookup('GetResponse'),

  SetRequest: root.lookup('SetRequest'),

  SetResponse: root.lookup('SetResponse'),

  //
  // Transaction
  TransactionHeader: root.lookup('TransactionHeader')
}
