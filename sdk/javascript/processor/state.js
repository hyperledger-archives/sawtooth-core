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

const {Entry, TpStateGetRequest, TpStateGetResponse, TpStateSetRequest, TpStateSetResponse, Message} = require('../protobuf')
const {InvalidTransaction} = require('../processor/exceptions')

const _timeoutPromise = (p, millis) => {
  if (millis !== null && millis !== undefined) {
    return Promise.race([
      new Promise((resolve, reject) => setTimeout(() => reject('Timeout occurred'), millis)),
      p])
  } else {
    return p
  }
}

class State {
  constructor (stream, contextId) {
    this._stream = stream
    this._contextId = contextId
  }

  /**
   * @param {string[]} addresses an array of address
   * @param {number} [timeout] - an optional timeout
   * @return a promise for a map of (address, buffer) pairs, where the buffer is
   * the encoded value at the specified address
   */
  get (addresses, timeout = null) {
    let getRequest = TpStateGetRequest.create({addresses, contextId: this._contextId})
    let future = this._stream.send(Message.MessageType.TP_STATE_GET_REQUEST,
                                   TpStateGetRequest.encode(getRequest).finish())
    return _timeoutPromise(
      future.then((buffer) => {
        let getResponse = TpStateGetResponse.decode(buffer)

        let results = {}
        getResponse.entries.forEach((entry) => {
          results[entry.address] = entry.data
        })
        if (getResponse.status === TpStateGetResponse.Status.AUTHORIZATION_ERROR) {
          throw new InvalidTransaction(`Tried to get unauthorized address ${addresses}`)
        }
        return results
      }),
      timeout)
  }

  /**
   * @param {Object} addressValuePairs - a map of (address, buffer) entries, where the
   * @param {number} [timeout] - an optional timeout
   * buffer is the encoded value to be set at the the given address.
   * @return a promise for the adddress successfully set.
   */
  set (addressValuePairs, timeout = null) {
    let entries = Object.keys(addressValuePairs).map((address) =>
      Entry.create({address, data: addressValuePairs[address]}))

    let setRequest = TpStateSetRequest.create({entries, contextId: this._contextId})
    let future = this._stream.send(Message.MessageType.TP_STATE_SET_REQUEST,
                                   TpStateSetRequest.encode(setRequest).finish())

    return _timeoutPromise(
      future.then((buffer) => {
        let setResponse = TpStateSetResponse.decode(buffer)
        if (setResponse.status === TpStateSetResponse.Status.AUTHORIZATION_ERROR) {
          let addresses = Object.keys(addressValuePairs)
          throw new InvalidTransaction(`Tried to set unauthorized address ${addresses}`)
        }
        return setResponse.addresses
      }),
      timeout)
  }
}

module.exports = State
