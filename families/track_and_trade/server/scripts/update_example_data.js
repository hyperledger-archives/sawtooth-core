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
const request = require('request-promise-native')
const { TransactionEncoder } = require('sawtooth-sdk')
const protos = require('../blockchain/protos')

const SERVER = process.env.SERVER || 'http://localhost:3000'
const DATA = process.env.DATA

if (DATA.indexOf('.json') === -1) {
  throw new Error('Use the "DATA" environment variable to specify a JSON file')
}

// How many times to send each update per minute
// If 0, will send LIMIT updates immediately, then exit
const RATE = process.env.RATE ? Number(process.env.RATE) : 6

// Maximum number of times to repeat each update
const LIMIT = process.env.LIMIT ? Number(process.env.LIMIT) : 25

const updateGroups = require(`./${DATA}`)
const VARIANCE_FACTOR = 0.75
let batcherPubkey = null

const createPayload = message => {
  return protos.TTPayload.encode(_.assign({
    timestamp: Math.floor(Date.now() / 1000)
  }, message)).finish()
}

const createTxn = (privateKey, payload) => {
  return new TransactionEncoder(privateKey, {
    familyName: 'track_and_trade',
    familyVersion: '1.0',
    payloadEncoding: 'application/protobuf',
    inputs: ['1c1108'],
    outputs: ['1c1108'],
    batcherPubkey
  }).create(payload)
}

const createUpdate = (privateKey, recordId, property) => {
  return createTxn(privateKey, createPayload({
    action: protos.TTPayload.Action.UPDATE_PROPERTIES,
    updateProperties: protos.UpdatePropertiesAction.create({
      recordId,
      properties: [protos.PropertyValue.create(property)]
    })
  }))
}

const submitTxns = txns => {
  const dummyPrivateKey = Array.apply(null, Array(64)).map(() => '1').join('')
  return request({
    method: 'POST',
    url: `${SERVER}/api/transactions?wait`,
    headers: { 'Content-Type': 'application/octet-stream' },
    encoding: null,
    body: new TransactionEncoder(dummyPrivateKey).encode(txns)
  })
  .catch(err => {
    console.error(err.response.body.toString())
    process.exit()
  })
}

const getVariance = max => {
  if (typeof max === 'object') return _.mapValues(max, getVariance)
  const variance = max * VARIANCE_FACTOR * Math.pow(Math.random(), 2)
  return Math.random() < 0.5 ? -variance : variance
}

const updateValue = (update, oldValue) => {
  if (typeof update.value === 'object') {
    return _.mapValues(update.value, (value, key) => {
      return updateValue(_.assign({}, update, { value }), oldValue[key])
    })
  }

  let value = getVariance(update.value)
  if (update.isAlwaysPositive) value = Math.abs(value)
  if (update.isAverage) value = update.value + value
  if (update.isRelative) value = oldValue + value
  return value
}

const updateProperty = (update, oldValue) => {
  oldValue = oldValue || update.startValue || null
  const { INT, FLOAT, LOCATION } = protos.PropertySchema.DataType
  const property = _.pick(update, 'name', 'dataType')

  if (property.dataType === INT) {
    property.intValue = parseInt(updateValue(update, oldValue || 0))

  } else if (property.dataType === FLOAT) {
    property.floatValue = updateValue(update, oldValue || 0)

  } else if (property.dataType === LOCATION) {
    const defaultLoc = { latitude: 0, longitude: 0 }
    const newLoc = updateValue(update, oldValue || defaultLoc)
    const intLoc = _.mapValues(newLoc, parseInt)

    if (intLoc.latitude > 90000000) intLoc.latitude = -90000000
    else if (intLoc.latitude < -90000000) intLoc.latitude = 90000000
    if (intLoc.longitude > 180000000) intLoc.longitude = -180000000
    else if (intLoc.longitude < -180000000) intLoc.longitude = 180000000

    property.locationValue = protos.Location.create(intLoc)

  } else if (property.name === 'tilt') {
    oldValue = JSON.parse(oldValue)

    const defaultTilt = { x: 0, y: 0 }
    const newTilt = updateValue(update, oldValue || defaultTilt)
    const intTilt = _.mapValues(newTilt, parseInt)

    property.stringValue = JSON.stringify(intTilt)

  } else if (property.name === 'shock') {
    oldValue = JSON.parse(oldValue)

    const defaultShock = { accel: 0, duration: 0 }
    const newShock = updateValue(update, oldValue || defaultShock)
    const intShock = _.mapValues(newShock, parseInt)

    property.stringValue = JSON.stringify(intShock)

  } else {
    throw new Error(`Bad update in JSON: ${property.name}`)
  }

  return property
}

const makeUpdateSubmitter = (count = 0) => () => {
  if (count >= LIMIT) return
  console.log(`Starting update set ${count + 1} of ${LIMIT}`)
  // Get current property values
  return request(`${SERVER}/api/records`)
    .then(res => {
      return JSON.parse(res).reduce((oldValues, record) => {
        return _.assign({
          [record.recordId]: _.zipObject(
            _.map(record.properties, prop => prop.name),
            _.map(record.properties, prop => prop.value))
        }, oldValues)
      }, {})
    })

    // Build update transactions
    .then(oldValues => {
      console.log(`Building updates . . .`)
      return updateGroups.reduce((updateTxns, group) => {
        group.updates.forEach(update => {
          if (update.noOpChance && Math.random() < update.noOpChance) return
          const oldValue = oldValues[group.recordId][update.name]
          const prop = updateProperty(update, oldValue)
          updateTxns.push(createUpdate(group.privateKey, group.recordId, prop))
        })
        return updateTxns
      }, [])
    })

    // Send update transactions
    .then(updateTxns => {
      console.log(`Submitting ${updateTxns.length} update transactions . . .`)
      submitTxns(updateTxns)
    })

    // Set timeout to call self
    .then(() => {
      console.log('Updates committed.')
      const wait = RATE ? 60000 / RATE : 0
      setTimeout(makeUpdateSubmitter(count + 1), wait)
    })
}

// Compile protos, fetch batcher pubkey, then begin submitting updates
protos.compile()
  .then(() => request(`${SERVER}/api/info`))
  .then(res => { batcherPubkey = JSON.parse(res).pubkey })
  .then(() => makeUpdateSubmitter()())
