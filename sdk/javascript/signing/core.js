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

/**
 * Thrown when trying to create a context for an algorithm which does not exist.
 */
class NoSuchAlgorithmError extends Error {
  /**
   * Constructs a new NoSuchAlgorithmError
   *
   * @param {string} [message] - an optional message, defaults to the empty
   * string
   */
  constructor (message = '') {
    super(message)
    this.name = this.constructor.name
  }
}

/**
 * Thrown when an error occurs during the signing process.
 */
class SigningError extends Error {
  /**
   * Constructs a new SigningError
   *
   * @param {string} [message] - an optional message, defaults to the empty
   * string
   */
  constructor (message = '') {
    super(message)
    this.name = this.constructor.name
  }
}

/**
 * Thrown when an error occurs during deserialization of a Private or Public
 * key from various formats.
 */
class ParseError extends Error {
  /**
   * Constructs a new ParseError
   *
   * @param {string} [message] - an optional message, defaults to the empty
   * string
   */
  constructor (message = '') {
    super(message)
    this.name = this.constructor.name
  }
}

/**
 * A private key instance.
 *
 * The underlying content is dependent on implementation.
 */
class PrivateKey {
  constructor () {
    if (this.constructor === PrivateKey) {
      throw new TypeError('Cannot construct abstract class')
    }
  }

  /**
   * Returns the algorithm name used for this private key.
   */
  getAlgorithmName () {
    throw new TypeError('Abstract method not implemented')
  }

  /**
   * Return the private key encoded as a hex string
   */
  asHex () {
    return this.asBytes().toString('hex')
  }

  /**
   * Returns the private key bytes in a Buffer.
   */
  asBytes () {
    throw new TypeError('Abstract method not implemented')
  }
}

/**
 * A public key instance.
 *
 * The underlying content is dependent on implementation.
 */
class PublicKey {
  constructor () {
    if (this.constructor === PublicKey) {
      throw new TypeError('Cannot construct abstract class')
    }
  }

  /**
   * Returns the algorithm name used for this public key.
   */
  getAlgorithmName () {
    throw new TypeError('Abstract method not implemented')
  }

  /**
   * Return the public key encoded as a hex string
   */
  asHex () {
    return this.asBytes().toString('hex')
  }

  /**
   * Returns the public key bytes in a Buffer.
   */
  asBytes () {
    throw new TypeError('Abstract method not implemented')
  }
}

/**
 * A context for a cryptographic signing algorithm.
 */
class Context {
  constructor () {
    if (this.constructor === Context) {
      throw new TypeError('Cannot construct abstract class')
    }
  }

  /**
   * Returns the algorithm name used for this context.
   */
  getAlgorithmName () {
    throw new TypeError('Abstract method not implemented')
  }

  /**
   * Sign a message.
   *
   * Given a private key for this algorithm, sign the given message bytes
   * and return a hex-encoded string of the resulting signature.
   *
   * @param {Buffer} message - the message bytes
   * @param {PrivateKey} privateKey - the private key
   *
   * @returns {string} - The signature in a hex-encoded string
   *
   * @throws {SigningError} - if any error occurs during the signing process
   */
  sign (message, privateKey) {
    throw new TypeError('Abstract method not implemented')
  }

  /**
   * Verifies that a signature of a message was produced with the associated
   * public key.
   *
   * @param {string} signature - the hex-encoded signature
   * @param {Buffer} message - the message bytes
   * @param {PublicKey} publicKey - the public key to use for verification
   *
   * @returns {boolean} - true if the public key is associated with the
   * signature for that method, false otherwise
   */
  verify (signature, message, publicKey) {
    throw new TypeError('Abstract method not implemented')
  }

  /**
   * Produce a public key for the given private key.
   *
   * @param {PrivateKey} privateKey - a private key
   *
   * @return {PublicKey} - the public key for the given private key
   */
  getPublicKey (privateKey) {
    throw new TypeError('Abstract method not implemented')
  }

  /**
   * Generate a new random private key, based on the underlying algorithm.
   *
   * @return {PrivateKey} - a private key instance
   */
  newRandomPrivateKey () {
    throw new TypeError('Abstract method not implemented')
  }
}

module.exports = {
  NoSuchAlgorithmError,
  SigningError,
  ParseError,
  PublicKey,
  PrivateKey,
  Context
}
