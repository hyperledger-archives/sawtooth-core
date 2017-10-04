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
 * ----------------------------------------------------------------------------
 */
'use strict'

const _ = require('lodash')
const { Stream } = require('sawtooth-sdk/messaging/stream')
const { Message } = require('sawtooth-sdk/protobuf')
const deltas = require('./deltas')
const batcher = require('./batcher')

const PREFIX = '1c1108'
const VALIDATOR_URL = process.env.VALIDATOR_URL || 'tcp://localhost:4004'
const stream = new Stream(VALIDATOR_URL)

// This workaround is necessary until delta protos are added to SDK
const protobuf = require('protobufjs')
const pbJson = require('sawtooth-sdk/protobuf/protobuf_bundle.json')
const root = protobuf.Root.fromJSON(pbJson)
const StateDeltaSubscribeRequest = root.lookup('StateDeltaSubscribeRequest')
const StateDeltaSubscribeResponse = root.lookup('StateDeltaSubscribeResponse')
const StateDeltaEvent = root.lookup('StateDeltaEvent')
const ClientBatchSubmitRequest = root.lookup('ClientBatchSubmitRequest')
const ClientBatchSubmitResponse = root.lookup('ClientBatchSubmitResponse')
const BatchStatus = root.lookup('BatchStatus')

const subscribe = () => {
  stream.connect(() => {
    // Set up onReceive handlers
    stream.onReceive(msg => {
      if (msg.messageType === Message.MessageType.STATE_DELTA_EVENT) {
        deltas.handle(StateDeltaEvent.decode(msg.content))
      } else {
        console.error('Received message of unknown type:', msg.messageType)
      }
    })

    // Send subscribe request
    stream.send(
      Message.MessageType.STATE_DELTA_SUBSCRIBE_REQUEST,
      StateDeltaSubscribeRequest.encode({ addressPrefixes: [PREFIX] }).finish()
    )
      .then(response => StateDeltaSubscribeResponse.decode(response))
      .then(decoded => {
        const status = _.findKey(StateDeltaSubscribeResponse.Status,
                                 val => val === decoded.status)
        if (status !== 'OK') {
          throw new Error(`Validator responded with status "${status}"`)
        }
      })
      .catch(err => console.error('Failed to subscribe to blockchain:',
                                  err.message))
  })
}

const submit = (txnBytes, { wait }) => {
  const batch = batcher.batch(txnBytes)

  return stream.send(
    Message.MessageType.CLIENT_BATCH_SUBMIT_REQUEST,
    ClientBatchSubmitRequest.encode({
      batches: [batch],
      waitForCommit: wait !== null,
      timeout: wait
    }).finish()
  )
  .then(response => ClientBatchSubmitResponse.decode(response))
  .then((decoded) => {
    const status = _.findKey(ClientBatchSubmitResponse.Status,
                             val => val === decoded.status)
    if (status !== 'OK') {
      throw new Error(`Batch submission failed with status '${status}'`)
    }

    if (wait === null) {
      return { batch: batch.headerSignature }
    }

    if (decoded.batchStatuses[0].status !== BatchStatus.Status.COMMITTED) {
      throw new Error(decoded.batchStatuses[0].invalidTransactions[0].message)
    }

    // Wait to return until new block is in database
    return new Promise(resolve => setTimeout(() => {
      resolve({ batch: batch.headerSignature })
    }, 1000))
  })
}

module.exports = {
  subscribe,
  submit
}
