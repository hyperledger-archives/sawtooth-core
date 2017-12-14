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

const { NoSuchAlgorithmError, SigningError, ParseError } = require('./core')
const secp256k1 = require('./secp256k1')

/**
 * A convenient wrapper of Context and PrivateKey
 */
class Signer {
  /**
   * Constructs a new Signer
   *
   * @param {Context} context - a cryptographic context
   * @param {PrivateKey} privateKey - private key
   */
  constructor (context, privateKey) {
    this._context = context
    this._privateKey = privateKey
    this._publicKey = null
  }

  /**
   * Signs the given message.
   *
   * @param {Buffer} message - the message bytes
   * @return {string} - the signature in a hex-encoded string
   * @throws {SigningError} - if any error occurs during the signing process
   */
  sign (message) {
    return this._context.sign(message, this._privateKey)
  }

  /**
   * Return the public key for this Signer instance.
   *
   * @return {PublicKey} the public key instance
   */
  getPublicKey () {
    if (this._publicKey === null) {
      this._publicKey = this._context.getPublicKey(this._privateKey)
    }

    return this._publicKey
  }
}

/**
 * Factory for generating signers.
 */
class CryptoFactory {
  /**
   * Constructs a CryptoFactory.
   *
   * @param {Context} context - a cryptographic context
   */
  constructor (context) {
    this._context = context
  }

  /**
   * Returns the context associated with this factory
   *
   * @return {Context}
   */
  getContext () {
    return this._context
  }

  /**
   * Create a new signer for the given private key.
   *
   * @param {PrivateKey} privateKey - a private key
   * @return {Signer} - a signer instance
   */
  newSigner (privateKey) {
    return new Signer(this._context, privateKey)
  }
}

/**
 * Returns an Context instance by algorithm name.
 *
 * @param {string} algorithmName - the algorithm name
 * @return {Context} a context instance for the given algorithm
 * @throws {NoSuchAlgorithmError} if the algorithm is unknown
 */
const createContext = algorithmName => {
  if (algorithmName === 'secp256k1') {
    return new secp256k1.Secp256k1Context()
  } else {
    throw new NoSuchAlgorithmError(`No such algorithm: ${algorithmName}`)
  }
}

module.exports = {
  // Re-export the errors
  NoSuchAlgorithmError,
  SigningError,
  ParseError,

  Signer,
  CryptoFactory,
  createContext
}
