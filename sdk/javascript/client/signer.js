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

const secp256k1 = require('secp256k1/js')
const {randomBytes, createHash} = require('crypto')

const _decodeBuffer = (buffer, format) => {
  if (buffer instanceof Buffer) return buffer
  return Buffer.from(buffer, format)
}

const _hashData = data => {
  const dataBuffer = _decodeBuffer(data, 'base64')
  return createHash('sha256').update(dataBuffer).digest()
}

const _decodeHex = hex => _decodeBuffer(hex, 'hex')

/** A static module with some useful cryptographic methods. */
module.exports = {
  /**
   * Sign data with a private key, using the secp256k1 elliptic.
   *
   * @param {Buffer|string} data - Data to be signed. May be encoded as
   *     either a raw binary Buffer, or a url-safe base64 string.
   * @param {string|Buffer} privateKey - 256-bit private key encoded as either
   *      a hex string or raw binary Buffer.
   *
   * @return {string} 512-bit signature represented as a 128-char hex string.
   */
  sign: (data, privateKey) => {
    const dataHash = _hashData(data)
    const keyBuffer = _decodeHex(privateKey)

    const signature = secp256k1.sign(dataHash, keyBuffer).signature
    return signature.toString('hex')
  },

  /**
   * Use a public key to verify a secp256k1 generated signature is valid.
   *
   * @param {Buffer|string} data - Data to be signed. May be encoded as either
   *     a raw binary Buffer, or a url-safe base64 string.
   * @param {string|Buffer} signature - A secp256k1 generated signature,
   *     encoded as either a hex string, or a raw binary Buffer.
   * @param {string|Buffer} publicKey - A secp256k1 public key, encoded as
   *     either a hex string, or a raw binary Buffer.
   *
   * @return {boolean} True if the signature is valid.
   */
  verify: (data, signature, publicKey) => {
    const dataHash = _hashData(data)
    const sigBuffer = _decodeHex(signature)
    const keyBuffer = _decodeHex(publicKey)

    return secp256k1.verify(dataHash, sigBuffer, keyBuffer)
  },

  /**
   * Generates a random 256-bit private key.
   *
   * @return {string} 256-bit private key represented as a 64-char hex string.
   */
  makePrivateKey: () => {
    let privateKey

    do privateKey = randomBytes(32)
    while (!secp256k1.privateKeyVerify(privateKey))

    return privateKey.toString('hex')
  },

  /**
   * Returns the safe to share public key for a 256-bit private key.
   *
   * @param {string|Buffer} privateKey - 256-bit private key encoded as either
   *      a hex string or raw binary Buffer.
   *
   * @return {string} Public key represented as a hex string.
   */
  getPublicKey: privateKey => {
    const privateBuffer = _decodeHex(privateKey)

    const publicKey = secp256k1.publicKeyCreate(privateBuffer)
    return publicKey.toString('hex')
  }
}
