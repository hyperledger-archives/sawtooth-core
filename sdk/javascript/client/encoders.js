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

const {createHash} = require('crypto')
const {Message} = require('protobufjs')

const signer = require('./signer')
const {
  TransactionHeader,
  Transaction,
  TransactionList,
  BatchHeader,
  Batch,
  BatchList
} = require('../protobuf')

const _arrayifyMessage = msg => msg instanceof Message ? [msg] : msg

const _generateNonce = () => {
  const dateString = Date.now().toString(36).slice(-5)
  const randomString = Math.floor(Math.random() * 46655).toString(36)
  return dateString + ('00' + randomString).slice(-3)
}

/** Defines an encoder to create multiple Transactions with common settings */
class TransactionEncoder {
  /**
   * Creates an encoder with a private key and template for default
   *     TransactionHeader values. A payloadEncoder may also be set in the
   *     template, to be run on each payload before wrapping in Transaction.
   *
   * @param {string|Buffer} privateKey - 256-bit private key encoded as either
   *      a hex string or binary Buffer.
   * @param {Object} [template={}] - Default values for each Transaction.
   * @param {string} [template.batcherPubkey] - Hex string encoded public key
   *     of the batcher, if not the same as the transaction encoder.
   * @param {string[]} [template.dependencies=[]] - Ids of Transactions that
   *     must be committed before Transactions created by encoder (unusual).
   * @param {string} [template.familyName=''] - Name of the transaction family.
   * @param {string} [template.familyVersion=''] - Version of the txn family.
   * @param {string[]} [template.inputs=[]] - Addresses to read from.
   * @param {string[]} [template.outputs=[]] - Addresses to write to.
   * @param {string} [template.payloadEncoding=''] - Encoding used on payload,
   *     for example: 'application/cbor'.
   * @param {function} [template.payloadEncoder] - A function that will encode
   *     payloads during transaction creation. For example, it might take an
   *     object, and return CBOR. If not set, the payload must be fully encoded
   *     before being passed to create.
   *
   * @return {TransactionEncoder} A TransactionEncoder instance.
   */
  constructor (privateKey, template = {}) {
    this._privateKey = privateKey
    this._publicKey = signer.getPublicKey(privateKey)
    this._payloadEncoder = template.payloadEncoder || (x => x)

    // TransactionHeader defaults can be modified after instantiation
    this.batcherPubkey = template.batcherPubkey || this._publicKey
    this.dependencies = template.dependencies || []
    this.familyName = template.familyName || ''
    this.familyVersion = template.familyVersion || ''
    this.inputs = template.inputs || []
    this.outputs = template.outputs || []
    this.payloadEncoding = template.payloadEncoding || ''
  }

  /**
   * Creates a signed instance of a Transaction. The payload will be encoded
   *     using the payload encoder provided at instantiation (if any). The
   *     TransactionHeader will be formed from whatever defaults were set
   *     at instantiation, overwritten by header settings are passed to this
   *     method call.
   *
   * @param {Buffer|*} payload - Payload to be submitted in the Transaction.
   *     If no payloadEncoder was set, it must be a binary Buffer.
   * @param {Object} [settings={}] - Values for the header of the Transaction.
   *     Overrides any template values set during encoder instantiation.
   * @param {string} [settings.batcherPubkey] - Hex string encoded public key
   *     of the batcher, if not the same as the transaction encoder.
   * @param {string[]} [settings.dependencies=[]] - Ids of Transactions that
   *     must be committed before this Transaction.
   * @param {string} [settings.familyName=''] - Name of the transaction family.
   * @param {string} [settings.familyVersion=''] - Version of the txn family.
   * @param {string[]} [settings.inputs=[]] - Addresses to read from.
   * @param {string[]} [settings.outputs=[]] - Addresses to write to.
   * @param {string} [settings.payloadEncoding=''] - Encoding used on payload,
   *     for example: 'application/cbor'.
   *
   * @return {Transaction} A new signed Transaction instance.
   */
  create (payload, settings = {}) {
    payload = this._payloadEncoder(payload)
    const payloadSha512 = createHash('sha512').update(payload).digest('hex')

    const header = TransactionHeader.encode({
      batcherPubkey: settings.batcherPubkey || this.batcherPubkey,
      dependencies: settings.dependencies || this.dependencies,
      familyName: settings.familyName || this.familyName,
      familyVersion: settings.familyVersion || this.familyVersion,
      inputs: settings.inputs || this.inputs,
      nonce: _generateNonce(),
      outputs: settings.outputs || this.outputs,
      payloadEncoding: settings.payloadEncoding || this.payloadEncoding,
      payloadSha512: payloadSha512,
      signerPubkey: this._publicKey
    }).finish()

    return Transaction.create({
      header,
      headerSignature: signer.sign(header, this._privateKey),
      payload: payload
    })
  }

  /**
   * Combines one or more Transactions into a TransactionList and encodes
   *     it for transmission to a batcher.
   *
   * @param {Transaction|Transaction[]} transactions - A Transaction instance,
   *     or array of Transactions.
   *
   * @return {Buffer} A binary Buffer of a TransactionList.
   */
  encode (transactions) {
    transactions = _arrayifyMessage(transactions)
    return TransactionList.encode({transactions}).finish()
  }

  /**
   * Creates a Transaction and wraps it as the only Transaction in a
   *     TransactionList encoded for transmission to a batcher.
   *
   * @param {Buffer|*} payload - Payload to be submitted in the Transaction.
   * @param {Object} [settings={}] - Values for the header of the Transaction.
   *     Properties are identical to `TransactionEncoder.create` above.
   *
   * @return {Buffer} A binary Buffer representation of a TransactionList.
   */
  createEncoded (payload, settings = {}) {
    const transaction = this.create(payload, settings)
    return this.encode(transaction)
  }
}

/** Defines BatchEncoders which combine Transactions and into Batches. */
class BatchEncoder {
  /**
   * Creates an encoder with a private key for signing Batches of Transactions.

   * @param {string|Buffer} privateKey - 256-bit private key encoded as either
   *      a hex string or binary Buffer.
   *
   * @return {BatchEncoder} A BatchEncoder instance.
   */
  constructor (privateKey) {
    this._privateKey = privateKey
    this._publicKey = signer.getPublicKey(privateKey)
  }

  /**
   * Creates and signs a new Batch from one or more Transactions.
   *
   * @param {Buffer|str|Transaction|Transaction[]} transactions - Transactions
   *     to be combined into a single Batch. The `batcher_pubkey` property in
   *     every Transactions' header must match this BatchEncoder's public key,
   *     or this Batch will be rejected by the validator.
   *
   *     This method accepts Transaction(s) in a number of formats:
   *         - TransactionList protobuf encoded as a Buffer
   *         - TransactionList protobuf encoded as a base64 string
   *         - Array of Transaction instances
   *         - Single Transaction instance
   *
   * @return {Batch} A new signed Batch instance.
   */
  create (transactions) {
    if (typeof transactions === 'string') {
      transactions = Buffer.from(transactions, 'base64')
    }

    if (transactions instanceof Buffer) {
      transactions = TransactionList.decode(transactions).transactions
    } else {
      transactions = _arrayifyMessage(transactions)
    }

    const header = BatchHeader.encode({
      signerPubkey: this._publicKey,
      transactionIds: transactions.map(t => t.headerSignature)
    }).finish()

    return Batch.create({
      header,
      headerSignature: signer.sign(header, this._privateKey),
      transactions
    })
  }

  /**
   * Combines one or more Batches into a BatchList, and encodes it for
   *     transmission to a validator.
   *
   * @param {Batch|Batch[]} batches - A Batch instance, or array of Batches.
   *
   * @return {Buffer} A binary Buffer representation of a BatchList.
   */
  encode (batches) {
    batches = _arrayifyMessage(batches)
    return BatchList.encode({batches}).finish()
  }

  /**
   * Creates a new Batch and then wraps it as the only one in a BatchList
   *     encoded for transmission to a validator.
   *
   * @param {Buffer|str|Transaction|Transaction[]} transactions - Transactions
   *     to be combined into a single Batch.
   *
   *     NOTE: The same formatting and signing rules for `BatchEncoder.create`
   *     above apply here.
   *
   * @return {Buffer} A binary Buffer representation of a BatchList.
   */
  createEncoded (transactions) {
    const batch = this.create(transactions)
    return this.encode(batch)
  }
}

module.exports = {TransactionEncoder, BatchEncoder}
