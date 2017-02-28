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
const zmq = require('zmq')

const util = require('util')
const assert = require('assert')

const {Message} = require('../protobuf')
const Future = require('./future')

const _encodeMessage = (messageType, correlationId, content) => {
  assert(util.isNumber(messageType))
  assert(util.isString(correlationId))
  assert(Buffer.isBuffer(content))

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
    this._socket = zmq.socket('dealer')
    this._socket.setsockopt('identity',
                            Buffer.from(this.constructor.name + uuid(), 'utf8'))
    this._futures = {}
  }

  connect () {
    this._socket.connect(this._url)
  }

  close () {
    this._socket.close()
  }

  send (type, content) {
    const correlationId = _generateId()
    let future = new Future()
    this._futures[correlationId] = future

    this._socket.send(_encodeMessage(type, correlationId, content))

    return future
  }

  sendBack (type, correlationId, content) {
    this._socket.send(_encodeMessage(type, correlationId, content))
  }

  onReceive (cb) {
    let self = this
    this._socket.on('message', buffer => {
      let message = Message.decode(buffer)
      if (self._futures[message.correlationId]) {
        self._futures[message.correlationId].set(message.content)
      } else {
        cb(message)
      }
    })
  }
}

module.exports = {Stream}
