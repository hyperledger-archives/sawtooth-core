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

const {
  signer,
  TransactionEncoder,
  BatchEncoder
} = require('sawtooth-sdk')
const protos = require('../blockchain/protos')

const privateKey = signer.makePrivateKey()
const encoder = new TransactionEncoder(privateKey, {
  familyName: 'track_and_trade',
  familyVersion: '1.0',
  payloadEncoding: 'application/protobuf',
  inputs: ['1c1108'],
  outputs: ['1c1108']
})
const batcher = new BatchEncoder(privateKey)

protos.compile()
  .then(() => {
    const { STRING, INT, LOCATION } = protos.PropertySchema.DataType

    const fishType = {
      name: 'fish',
      properties: [{
        name: 'species',
        dataType: STRING,  // 3-letter ASFIS code
        required: true
      }, {
        name: 'length',
        dataType: INT,  // millionths of a meter (micrometer)
        required: true
      }, {
        name: 'weight',
        dataType: INT,  // millionths of a kg (milligram)
        required: true
      }, {
        name: 'location',
        dataType: LOCATION,
        required: true
      }, {
        name: 'temperature',
        dataType: INT,  // millionths of a degree C
        required: false
      }, {
        name: 'tilt',
        dataType: STRING,  // JSON with integers 'X' and 'Y'
        required: false
      }, {
        name: 'shock',
        dataType: STRING,  // JSON with integers 'Accel' and 'Duration'
        required: false
      }]
    }

    const agentPayload = protos.TTPayload.encode({
      action: protos.TTPayload.Action.CREATE_AGENT,
      timestamp: Math.floor(Date.now() / 1000),
      createAgent: protos.CreateAgentAction.create({
        name: 'FishNet Admin'
      })
    }).finish()

    const typePayload = protos.TTPayload.encode({
      action: protos.TTPayload.Action.CREATE_RECORD_TYPE,
      timestamp: Math.floor(Date.now() / 1000),
      createRecordType: protos.CreateRecordTypeAction.create({
        name: fishType.name,
        properties: fishType.properties.map(prop => {
          return protos.PropertySchema.create(prop)
        })
      })
    }).finish()

    const txns = [
      encoder.create(agentPayload),
      encoder.create(typePayload)
    ]

    const batch = batcher.createEncoded(txns)

    process.stdout.write(batch)
  })
