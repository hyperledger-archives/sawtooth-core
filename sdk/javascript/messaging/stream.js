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

const crypto = require('crypto')
const uuid = require('uuid/v4')
const zmq = require('zeromq')

const assert = require('assert')

const { Message } = require('../protobuf')
const Deferred = require('./deferred')
const { ValidatorConnectionError } = require('../processor/exceptions')

const _encodeMessage = (messageType, correlationId, content) => {
  assert(
    typeof messageType === 'number',
    `messageType must be a number; was ${messageType}`
  )
  assert(
    typeof correlationId === 'string',
    `correlationId must be a string; was ${correlationId}`
  )
  assert(
    content !== undefined || content !== null,
    'content must not be null or undefined'
  )
  assert(
    Buffer.isBuffer(content),
    `content must be a buffer; was ${
      content.constructor ? content.constructor.name : typeof content
    }`
  )

  return Message.encode({
    messageType,
    correlationId,
    content
  }).finish()
}

const _generateId = () =>
  crypto.createHash('sha256')
    .update(uuid())
    .digest('hex')

class Stream {
  constructor (url) {
    this._url = url

    this._initial_connection = true
  }

  connect (onConnectCb) {
    if (this._onConnectCb) {
      console.log(`Attempting to reconnect to ${this._url}`)
    }

    this._onConnectCb = onConnectCb

    this._futures = {}
    this._socket = zmq.socket('dealer')
    this._socket.setsockopt('identity', Buffer.from(uuid(), 'utf8'))
    this._socket.on('connect', () => {
      console.log(`Connected to ${this._url}`)
      onConnectCb()
    })
    this._socket.on('disconnect', (fd, endpoint) => this._handleDisconnect())
    this._socket.monitor(250, 0)
    this._socket.connect(this._url)

    this._initial_connection = false
  }

  close () {
    this._socket.setsockopt(zmq.ZMQ_LINGER, 0)
    this._socket.unmonitor()
    this._socket.close()
    this._socket = null
  }

  _handleDisconnect () {
    console.log(`Disconnected from ${this._url}`)
    this.close()
    Object.keys(this._futures).forEach((correlationId) => {
      this._futures[correlationId].reject(
        new ValidatorConnectionError('The connection to the validator was lost')
      )
    })

    this.connect(this._onConnectCb)
  }

  send (type, content) {
    if (this._socket) {
      const correlationId = _generateId()
      let deferred = new Deferred()
      this._futures[correlationId] = deferred

      try {
        this._socket.send(_encodeMessage(type, correlationId, content))
      } catch (e) {
        delete this._futures[correlationId]
        return Promise.reject(e)
      }

      return deferred.promise
        .then(result => {
          delete this._futures[correlationId]
          return result
        })
        .catch(err => {
          delete this._futures[correlationId]
          throw err
        })
    } else {
      let err = null
      if (this._initial_connection) {
        err = new Error('Must call `connect` before calling `send`')
      } else {
        err = new ValidatorConnectionError(
          'The connection to the validator was lost'
        )
      }

      return Promise.reject(err)
    }
  }

  sendBack (type, correlationId, content) {
    if (this._socket) {
      this._socket.send(_encodeMessage(type, correlationId, content))
    }
  }

  onReceive (cb) {
    this._socket.on('message', buffer => {
      let message = Message.decode(buffer)
      if (this._futures[message.correlationId]) {
        this._futures[message.correlationId].resolve(message.content)
      } else {
        process.nextTick(() => cb(message))
      }
    })
  }
}

module.exports = { Stream }
