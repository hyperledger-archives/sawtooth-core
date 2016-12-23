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

const {TransactionHandler} = require('sawtooth-sdk/processor')
const {InvalidTransaction, InternalError} = require('sawtooth-sdk/processor/exceptions')

const crypto = require('crypto')
const cbor = require('cbor')

const _hash = (x) =>
  crypto.createHash('sha512').update(x).digest('hex').toLowerCase()

const INT_KEY_FAMILY = 'intkey'
const INT_KEY_NAMESPACE = _hash(INT_KEY_FAMILY).substring(0, 6)

const _decodeCbor = (buffer) =>
  new Promise((resolve, reject) =>
              cbor.decodeFirst(buffer, (err, obj) => err ? reject(err) : resolve(obj)))

const _toInternalError = (err) => {
  let message = (err.message) ? err.message : err
  throw new InternalError(message)
}

const _setEntry = (state, address, stateValue) => {
  let entries = {
    [address]: cbor.encode(stateValue)
  }
  return state.set(entries)
}

const _handleSet = (state, address, name, value) => (possibleAddressValues) => {
  let stateValueRep = possibleAddressValues[address]

  let stateValue
  if (stateValueRep && stateValueRep.length > 0) {
    stateValue = cbor.decodeFirstSync(stateValueRep)
    if (stateValue[name]) {
      throw new InvalidTransaction(
        `Verb is set but Name already in state, Name: ${name} Value: ${stateValue[name]}`)
    }
  }

  if (value < 0) {
    throw new InvalidTransaction('Verb is set but Value is less than 0')
  }
  // 'set' passes checks so store it in the state
  if (!stateValue) {
    stateValue = {}
  }

  stateValue[name] = value

  return _setEntry(state, address, stateValue)
}

const _handleOperator = (verb, op) => (state, address, name, value) => (possibleAddressValues) => {
  let stateValueRep = possibleAddressValues[address]
  if (!stateValueRep || stateValueRep.length === 0) {
    throw new InvalidTransaction(`Verb is ${verb} but Name is not in state`)
  }

  let stateValue = cbor.decodeFirstSync(stateValueRep)
  if (!stateValue[name]) {
    throw new InvalidTransaction(`Verb is ${verb} but Name is not in state`)
  }

  // Increment the value in state by value
  stateValue[name] = op(stateValue[name], value)
  return _setEntry(state, address, stateValue)
}

const _handleInc = _handleOperator('inc', (x, y) => x + y)
const _handleDec = _handleOperator('dec', (x, y) => x - y)

class IntegerKeyHandler extends TransactionHandler {
  constructor () {
    super(INT_KEY_FAMILY, '1.0', 'application/cbor', [INT_KEY_NAMESPACE])
  }

  apply (transactionProcessRequest, state) {
    return _decodeCbor(transactionProcessRequest.payload)
      .catch(_toInternalError)
      .then((update) => {
        //
        // Validate the update
        let name = update.Name
        if (!name) {
          throw new InvalidTransaction('Name is required')
        }

        let verb = update.Verb
        if (!verb) {
          throw new InvalidTransaction('Verb is required')
        }

        let value = update.Value
        if (!value) {
          throw new InvalidTransaction('Value is required')
        }
        value = parseInt(value)
        if (isNaN(value)) {
          throw new InvalidTransaction('Value must be an integer')
        }

        //
        // Perform the action

        let handlerFn
        if (verb === 'set') {
          handlerFn = _handleSet
        } else if (verb === 'dec') {
          handlerFn = _handleDec
        } else if (verb === 'inc') {
          handlerFn = _handleInc
        } else {
          throw new InvalidTransaction(`Verb must be set, inc, dec not ${verb}`)
        }

        let address = INT_KEY_NAMESPACE + _hash(name)

        return state.get([address]).then(handlerFn(state, address, name, value))
          .then((addresses) => {
            if (addresses.length === 0) {
              throw new InternalError('State Error!')
            }
            // TODO: Use some form of logging
            console.log(`Verb: ${verb} Name: ${name} Value: ${value}`)
          })
      })
  }

}

module.exports = IntegerKeyHandler
