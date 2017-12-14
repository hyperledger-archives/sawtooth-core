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

const {
  TpStateEntry,
  TpStateGetRequest,
  TpStateGetResponse,
  TpStateSetRequest,
  TpStateSetResponse,
  TpStateDeleteRequest,
  TpStateDeleteResponse,
  TpReceiptAddDataRequest,
  TpReceiptAddDataResponse,
  Event,
  TpEventAddRequest,
  TpEventAddResponse,
  Message
} = require('../protobuf')

const {
  AuthorizationException,
  InternalError
} = require('../processor/exceptions')

const _timeoutPromise = (p, millis) => {
  if (millis !== null && millis !== undefined) {
    return Promise.race([
      new Promise(
        (resolve, reject) =>
          setTimeout(() => reject(Error('Timeout occurred')), millis)
      ),
      p
    ])
  } else {
    return p
  }
}

/**
 * Context provides an interface for getting and setting validator
 * state. All validator interactions by a handler should be through
 * a Context instance.
 */
class Context {
  constructor (stream, contextId) {
    this._stream = stream
    this._contextId = contextId
  }

  /**
   * getState queries the validator state for data at each of the
   * addresses in the given list. The addresses that have been set are
   * returned in a list.
   *
   * @param {string[]} addresses an array of addresses
   * @param {number} [timeout] - an optional timeout
   * @return a promise for a map of (address, buffer) pairs, where the
   * buffer is the encoded value at the specified address
   * @throws {AuthorizationException}
   */
  getState (addresses, timeout = null) {
    let getRequest = TpStateGetRequest.create({
      addresses,
      contextId: this._contextId
    })
    let future = this._stream.send(
      Message.MessageType.TP_STATE_GET_REQUEST,
      TpStateGetRequest.encode(getRequest).finish()
    )
    return _timeoutPromise(
      future.then(buffer => {
        let getResponse = TpStateGetResponse.decode(buffer)

        let results = {}
        getResponse.entries.forEach(entry => {
          results[entry.address] = entry.data
        })
        if (
          getResponse.status === TpStateGetResponse.Status.AUTHORIZATION_ERROR
        ) {
          throw new AuthorizationException(
            `Tried to get unauthorized address ${addresses}`
          )
        }
        return results
      }),
      timeout)
  }

  /**
   * setState requests that each address in the provided dictionary
   * be set in validator state to its corresponding value. A list is
   * returned containing the successfully set addresses.

   * @param {Object} addressValuePairs - a map of (address, buffer)
   * entries, where the buffer is the encoded value to be set at the
   * the given address.
   * @param {number} [timeout] - an optional timeout
   * @return a promise for the adddresses successfully set.
   * @throws {AuthorizationException}
   */
  setState (addressValuePairs, timeout = null) {
    let entries = Object.keys(addressValuePairs).map((address) =>
      TpStateEntry.create({address, data: addressValuePairs[address]}))

    let setRequest = TpStateSetRequest.create({
      entries,
      contextId: this._contextId
    })
    let future = this._stream.send(
      Message.MessageType.TP_STATE_SET_REQUEST,
      TpStateSetRequest.encode(setRequest).finish()
    )

    return _timeoutPromise(
      future.then((buffer) => {
        let setResponse = TpStateSetResponse.decode(buffer)
        if (setResponse.status === TpStateSetResponse.Status.AUTHORIZATION_ERROR) {
          let addresses = Object.keys(addressValuePairs)
          throw new AuthorizationException(
            `Tried to set unauthorized address ${addresses}`
          )
        }
        return setResponse.addresses
      }),
      timeout)
  }

  /**
   * deleteState requests that each of the provided addresses be
   * unset in validator state. A list of successfully deleted
   * addresses is returned.
   *
   * @param {string[]} addresses -  an array of addresses
   * @param {number} [timeout] - an optional timeout
   * @return a promise for the adddresses successfully deleted.
   * @throws {AuthorizationException}
   */
  deleteState (addresses, timeout = null) {
    let getRequest = TpStateDeleteRequest.create({
      addresses,
      contextId: this._contextId
    })
    let future = this._stream.send(
      Message.MessageType.TP_STATE_DELETE_REQUEST,
      TpStateDeleteRequest.encode(getRequest).finish()
    )
    return _timeoutPromise(
      future.then((buffer) => {
        let deleteResponse = TpStateDeleteResponse.decode(buffer)

        if (
          deleteResponse.status ===
          TpStateDeleteResponse.Status.AUTHORIZATION_ERROR
        ) {
          throw new AuthorizationException(
            `Tried to delete unauthorized address ${addresses}`
          )
        }
        return deleteResponse.addresses
      }),
      timeout)
  }

  /**
   * Add a blob to the execution result for this transaction.
   *
   * @param {Buffer} data - the data to add
   * @param {number} [timeout] - an optional timeout
   * @return {Promise} a promise that resolves to nothing on success, or an
   * error if the operation fails
   */
  addReceiptData (data, timeout = null) {
    let addReceiptRequest = TpReceiptAddDataRequest.create({
      contextId: this._contextId,
      data
    })

    let future = this._stream.send(
      Message.MessageType.TP_RECEIPT_ADD_DATA_REQUEST,
      TpReceiptAddDataRequest.encode(addReceiptRequest).finish()
    )

    return _timeoutPromise(
      future.then((buffer) => {
        let response = TpReceiptAddDataResponse.decode(buffer)

        if (response.status !== TpReceiptAddDataResponse.Status.OK) {
          throw new InternalError('Failed to add receipt data')
        }
      }),
      timeout)
  }

  /**
   * Add a new event to the execution result for this transaction.
   *
   * @param {string} eventType - This is used to subscribe to events. It should
   * be globally unique and describe what, in general, has occurred
   * @param {string[][]} attributes - Additional information about the event that
   * is transparent to the validator.  Attributes can be used by subscribers to
   * filter the type of events they receive.
   * @param {Buffer} data - Additional information about the event that is
   * opaque to the validator.
   * @param {number} [timeout] - an optional timeout
   * @return {Promise} a promise that resolves to nothing on success, or an
   * error if the operation fails
   */
  addEvent (eventType, attributes, data, timeout = null) {
    if (attributes === null || attributes === undefined) {
      attributes = []
    }

    let event = Event.create({
      eventType,
      attributes: attributes.map(
        ([ key, value ]) => Event.Attribute.create({ key, value })
      ),
      data
    })

    let request = TpEventAddRequest.encode({
      contextId: this._contextId,
      event
    }).finish()

    let future = this._stream.send(
      Message.MessageType.TP_EVENT_ADD_REQUEST,
      request
    )

    return _timeoutPromise(
      future.then((buffer) => {
        let response = TpEventAddResponse.decode(buffer)

        if (response.status !== TpEventAddResponse.Status.OK) {
          throw new InternalError(`Failed to add event: ${eventType}`)
        }
      }),
      timeout)
  }
}

module.exports = Context
