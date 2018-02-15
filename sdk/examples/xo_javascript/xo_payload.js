/**
 * Copyright 2018 Intel Corporation
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

const { InvalidTransaction } = require('sawtooth-sdk/processor/exceptions')

class XoPayload {
  fromBytes (payload) {
    return this._decodeRequest(payload)
  }

  _decodeRequest (payload) {
    return new Promise((resolve, reject) => {
      payload = payload.toString().split(',')
      if (payload.length === 3) {
        resolve({
          name: payload[0],
          action: payload[1],
          space: payload[2]
        })
      } else {
        let reason = new InvalidTransaction('Invalid payload serialization')
        reject(reason)
      }
    })
  }
}

module.exports = XoPayload
