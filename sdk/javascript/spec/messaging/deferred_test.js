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
 * ------------------------------------------------------------------------------
 */

'use strict'

const assert = require('assert')

const Deferred = require('../../messaging/deferred')

describe('Deferred', () => {
  describe('resolve', () => {
    it('should immediately return the value of a resolved deferred', () => {
      let deferred = new Deferred()

      deferred.resolve('my result')

      return deferred.promise.then((result) => {
        assert.equal('my result', result)
      })
    })

    it('should not return until resolved.', () => {
      let deferred = new Deferred()

      let promise = deferred.promise.then((result) => {
        assert.equal('my result', result)
      })

      deferred.resolve('my result')

      return promise
    })
  })

  describe('reject', () => {
    it('should return a undefined error when none is set', (done) => {
      let deferred = new Deferred()

      deferred.promise.catch((e) => {
        assert.equal(undefined, e)
        done()
      })
      .then(() => {
        assert.ok(false, 'Did not catch')
      })

      deferred.reject()
    })

    it('should return the error when one is set', (done) => {
      let deferred = new Deferred()

      deferred.promise.catch((e) => {
        assert.equal('my error msg', e.message)
        done()
      })
      .then(() => {
        assert.ok(false, 'Did not catch')
      })

      deferred.reject(new Error('my error msg'))
    })
  })
})
