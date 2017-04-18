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
const {range} = require('underscore')
const {randomBytes} = require('crypto')

const {signer, BatchEncoder, TransactionEncoder} = require('../../client')

const {
  TransactionHeader,
  TransactionList,
  BatchHeader,
  BatchList
} = require('../../protobuf')

describe('TransactionEncoder', () => {
  const privateKey = signer.makePrivateKey()
  const publicKey = signer.getPublicKey(privateKey)

  describe('create', () => {
    const headerTemplate = {
      batcherPubkey: 'test',
      familyName: 'test',
      familyVersion: 'test',
      inputs: ['test'],
      outputs: ['test'],
      payloadEncoding: 'test',
      badTemplateKey: 'bad'
    }

    it('should create a basic Transaction with stringified data', () => {
      const transactor = new TransactionEncoder(privateKey)
      const payload = randomBytes(100).toString('base64')
      const txn = transactor.create(payload)

      assert.equal(payload, txn.payload, 'payload does not match')
      assert(
        signer.verify(txn.header, txn.headerSignature, publicKey),
        'Transaction header signature is not valid'
      )
    })

    it('should create a basic Transaction with raw Buffers', () => {
      const transactor = new TransactionEncoder(Buffer.from(privateKey, 'hex'))
      const payload = randomBytes(100)
      const txn = transactor.create(payload)

      assert.equal(payload, txn.payload, 'payload does not match')
      assert(
        signer.verify(txn.header, txn.headerSignature, publicKey),
        'Transaction header signature is not valid'
      )
    })

    it('should apply a preset encoder to Transaction payloads', () => {
      const transactor = new TransactionEncoder(privateKey, {
        payloadEncoder: Buffer.from
      })
      const payload = 'test'
      const txn = transactor.create(payload)

      assert(txn.payload instanceof Buffer, 'payload was not encoded')
      assert.equal('test', txn.payload.toString(), 'payload does not match')
    })

    it('should create a templated Transaction', () => {
      const transactor = new TransactionEncoder(privateKey, headerTemplate)
      const payload = randomBytes(100)
      const txn = transactor.create(payload)

      const header = TransactionHeader.decode(txn.header)
      assert.equal('test', header.batcherPubkey)
      assert.equal('test', header.familyName)
      assert.equal('test', header.familyVersion)
      assert.deepEqual(['test'], header.inputs)
      assert.deepEqual(['test'], header.outputs)
      assert.equal('test', header.payloadEncoding)
      assert.equal(undefined, header.badTemplateKey)

      assert(
        signer.verify(txn.header, txn.headerSignature, publicKey),
        'Transaction header signature is not valid'
      )
    })

    it('should override template keys when creating a Transaction', () => {
      const transactor = new TransactionEncoder(privateKey, headerTemplate)
      const payload = randomBytes(100)

      const txn = transactor.create(payload, {
        batcherPubkey: 'new',
        familyName: 'new',
        familyVersion: 'new',
        inputs: ['new'],
        outputs: ['new'],
        payloadEncoding: 'new'
      })

      const header = TransactionHeader.decode(txn.header)
      assert.equal('new', header.batcherPubkey)
      assert.equal('new', header.familyName)
      assert.equal('new', header.familyVersion)
      assert.deepEqual(['new'], header.inputs)
      assert.deepEqual(['new'], header.outputs)
      assert.equal('new', header.payloadEncoding)

      assert(
        signer.verify(txn.header, txn.headerSignature, publicKey),
        'Transaction header signature is not valid'
      )
    })
  })

  describe('encode', () => {
    it('should encode a Transaction as a TransactionList binary', () => {
      const transactor = new TransactionEncoder(privateKey)
      const txn = transactor.create(randomBytes(100))

      const encoded = transactor.encode(txn)
      assert(encoded instanceof Buffer, 'TransactionList was not encoded')

      const decoded = TransactionList.decode(encoded).transactions[0]
      assert.deepEqual(txn, decoded, 'decoded Transaction does not match')
    })

    it('should encode multiple Transactions in TransactionList binary', () => {
      const transactor = new TransactionEncoder(privateKey)
      const txns = range(10).map(() => transactor.create(randomBytes(100)))

      const encoded = transactor.encode(txns)
      assert(encoded instanceof Buffer, 'TransactionList was not encoded')

      const decoded = TransactionList.decode(encoded).transactions
      assert.deepEqual(txns, decoded, 'TransactionList does not match')
    })
  })

  describe('createEncoded', () => {
    it('should create a Transaction wrapped in TransactionList binary', () => {
      const transactor = new TransactionEncoder(privateKey)

      const encoded = transactor.createEncoded(Buffer.from('test'))
      assert(encoded instanceof Buffer, 'TransactionList was not encoded')

      const decoded = TransactionList.decode(encoded).transactions[0]
      const decodedPayload = decoded.payload.toString()
      assert.equal('test', decodedPayload, 'payload doesnt match')
    })
  })
})

describe('BatchEncoder', () => {
  const privateKey = signer.makePrivateKey()
  const publicKey = signer.getPublicKey(privateKey)

  describe('create', () => {
    const transactorKey = signer.makePrivateKey()

    it('should create a Batch from a single of Transactions', () => {
      const transactor = new TransactionEncoder(privateKey)
      const batcher = new BatchEncoder(privateKey)

      const txn = transactor.create(randomBytes(100))
      const batch = batcher.create(txn)

      assert.deepEqual(txn, batch.transactions[0], 'Txn does not match')
      assert(
        signer.verify(batch.header, batch.headerSignature, publicKey),
        'Batch header signature is not valid'
      )

      const header = BatchHeader.decode(batch.header)
      assert.equal(
        txn.headerSignature,
        header.transactionIds[0],
        'Transaction id does not match'
      )
    })

    it('should create a Batch from multiple Transactions', () => {
      const transactor = new TransactionEncoder(privateKey)
      const batcher = new BatchEncoder(privateKey)

      const txns = range(10).map(() => transactor.create(randomBytes(100)))
      const batch = batcher.create(txns)

      assert.deepEqual(txns, batch.transactions, 'Transactions do not match')
      assert(
        signer.verify(batch.header, batch.headerSignature, publicKey),
        'Batch header signature is not valid'
      )

      const header = BatchHeader.decode(batch.header)
      assert.equal(10, header.transactionIds.length, 'expected ten Txn ids')
      assert.equal(
        txns[0].headerSignature,
        header.transactionIds[0],
        'Transaction id does not match'
      )
    })

    it('should create a Batch from a binary TransactionList', () => {
      const transactor = new TransactionEncoder(transactorKey, {
        batcherPubkey: publicKey
      })
      const batcher = new BatchEncoder(privateKey)

      const txn = transactor.create(randomBytes(100))
      const encoded = transactor.encode(txn)
      const batch = batcher.create(encoded)

      assert.deepEqual(txn, batch.transactions[0], 'Txn does not match')
      assert(
        signer.verify(batch.header, batch.headerSignature, publicKey),
        'Batch header signature is not valid'
      )

      const header = BatchHeader.decode(batch.header)
      assert.equal(
        txn.headerSignature,
        header.transactionIds[0],
        'Transaction id does not match'
      )
    })

    it('should create a Batch from a base64 TransactionList', () => {
      const transactor = new TransactionEncoder(transactorKey, {
        batcherPubkey: publicKey
      })
      const batcher = new BatchEncoder(privateKey)

      const txn = transactor.create(randomBytes(100))
      const stringified = transactor.encode(txn).toString('base64')
      const batch = batcher.create(stringified)

      assert.deepEqual(txn, batch.transactions[0], 'Txn does not match')
      assert(
        signer.verify(batch.header, batch.headerSignature, publicKey),
        'Batch header signature is not valid'
      )

      const header = BatchHeader.decode(batch.header)
      assert.equal(
        txn.headerSignature,
        header.transactionIds[0],
        'Transaction id does not match'
      )
    })
  })

  describe('encode', () => {
    it('should wrap a Batch in an encoded BatchList', () => {
      const transactor = new TransactionEncoder(privateKey)
      const batcher = new BatchEncoder(privateKey)

      const txn = transactor.create(randomBytes(100))
      const batch = batcher.create(txn)

      const encoded = batcher.encode(batch)
      assert(encoded instanceof Buffer, 'BatchList was not encoded')

      const decoded = BatchList.decode(encoded)
      assert.deepEqual(batch, decoded.batches[0], 'Batch does not match')
    })

    it('should wrap multiple Batches in an encoded BatchList', () => {
      const transactor = new TransactionEncoder(privateKey)
      const batcher = new BatchEncoder(privateKey)

      const txn = transactor.create(randomBytes(100))
      const batches = range(10).map(() => batcher.create(txn))

      const encoded = batcher.encode(batches)
      assert(encoded instanceof Buffer, 'BatchList was not encoded')

      const decoded = BatchList.decode(encoded)
      assert.deepEqual(batches, decoded.batches, 'Batches do not match')
    })
  })

  describe('createEncoded', () => {
    it('should wrap a Batch wrapped in a BatchList binary', () => {
      const transactor = new TransactionEncoder(privateKey)
      const batcher = new BatchEncoder(privateKey)
      const txn = transactor.create(Buffer.from('test'))

      const encoded = batcher.createEncoded(txn)
      assert(encoded instanceof Buffer, 'BatchList was not encoded')

      const decoded = BatchList.decode(encoded).batches[0]
      const decodedPayload = decoded.transactions[0].payload.toString()
      assert.deepEqual('test', decodedPayload, 'Payload does not match')
    })
  })
})
