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
const blocks = require('../db/blocks')
const state = require('../db/state')
const protos = require('./protos')

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

const getProtoName = address => {
  const typePrefix = address.slice(6, 8)
  if (typePrefix === 'ea') {
    if (address.slice(-4) === '0000') return 'Property'
    else return 'PropertyPage'
  }

  const names = {
    ae: 'Agent',
    aa: 'Proposal',
    ec: 'Record',
    ee: 'RecordType'
  }
  if (names[typePrefix]) return names[typePrefix]

  throw new Error(`Blockchain Error: No Protobuf for prefix "${typePrefix}"`)
}

const getObjectifier = address => {
  const name = getProtoName(address)
  return stateInstance => {
    const obj = protos[name].toObject(stateInstance, {
      enums: String,  // use string names for enums
      longs: Number,  // convert int64 to Number, limiting precision to 2^53
      defaults: true  // use default for falsey values
    })
    if (name === 'PropertyPage') {
      obj.pageNum = parseInt(address.slice(-4), 16)
    }
    return obj
  }
}

const getAdder = address => {
  const addState = state[`add${getProtoName(address)}`]
  const toObject = getObjectifier(address)
  return (stateInstance, blockNum) => {
    addState(toObject(stateInstance), blockNum)
  }
}

const getEntries = ({ address, value }) => {
  return protos[`${getProtoName(address)}Container`]
    .decode(value)
    .entries
}

const handleDeltaEvent = content => {
  const event = StateDeltaEvent.decode(content)
  return Promise.all(event.stateChanges.map(change => {
    const addState = getAdder(change.address)
    return Promise.all(getEntries(change).map(entry => {
      return addState(entry, event.blockNum)
    }))
  }))
    .then(() => {
      return blocks.insert(
        _.pick(event, 'blockNum', 'blockId', 'stateRootHash')
      )
    })
    .then(() => event)
}

const subscribe = () => {
  stream.connect(() => {
    // Set up onReceive handlers
    stream.onReceive(msg => {
      if (msg.messageType === Message.MessageType.STATE_DELTA_EVENT) {
        handleDeltaEvent(msg.content)
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
        if (decoded.status !== StateDeltaSubscribeResponse.Status.OK) {
          console.error('Failed to subscribe to blockchain, with status:',
                        decoded.status)
        }
      })
      .catch(err => console.error('Failed to subscribe to blockchain:', err))
  })
}

module.exports = {
  subscribe
}
