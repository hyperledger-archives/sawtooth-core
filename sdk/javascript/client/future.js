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

//
// TODO: Timeouts

const _handleResult = (self, f) => (v) => {
  self._isDone = true
  self._value = v
  return f(v)
}

class Future {
  constructor () {
    let self = this
    this._promise = new Promise((resolve, reject) => {
      self._resolver = resolve
    })
  }

  get (f) {
    if (this._isDone) {
      return f(this._value)
    } else {
      return this._promise.then(_handleResult(this, f))
    }
  }

  set (value) {
    if (!this._isDone) {
      this._resolver(value)
    }
  }

  then (f) {
    return this._promise.then(_handleResult(this, f))
  }

  catch (f) {
    return this._promise.catch(f)
  }
}

module.exports = Future
