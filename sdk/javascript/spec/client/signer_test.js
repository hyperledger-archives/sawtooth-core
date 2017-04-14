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
const {randomBytes} = require('crypto')
const signer = require('../../client/signer')

const _hexToBinary = hex => {
  return Buffer.from(hex, 'hex')
}

describe('Signer', () => {
  it('with raw binaries, should make keys, sign, and verify data', () => {
    const data = randomBytes(100)
    const privateKey = _hexToBinary(signer.makePrivateKey())
    const publicKey = _hexToBinary(signer.getPublicKey(privateKey))
    const signature = _hexToBinary(signer.sign(data, privateKey))

    assert(
      signer.verify(data, signature, publicKey),
      'signature did not pass verification'
    )
  })

  it('with string representations, should make keys, sign, and verify', () => {
    const data = randomBytes(100).toString('base64')
    const privateKey = signer.makePrivateKey()
    const publicKey = signer.getPublicKey(privateKey)
    const signature = signer.sign(data, privateKey)

    assert(
      signer.verify(data, signature, publicKey),
      'signature did not pass verification'
    )
  })
})
