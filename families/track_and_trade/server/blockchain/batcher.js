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
 * ----------------------------------------------------------------------------
 */
'use strict'

const { signer, BatchEncoder } = require('sawtooth-sdk')
const { TransactionHeader, TransactionList } = require('sawtooth-sdk/protobuf')

let PRIVATE_KEY = process.env.PRIVATE_KEY
if (PRIVATE_KEY === undefined) {
  PRIVATE_KEY = '660f60b1f33a19f5f24d5c4d963a012a1e58241626d4df851e2dbe0f2a3b222e'
  console.warn(`No batch signing key provided, defaulting to "${PRIVATE_KEY}"`)
  console.warn('Use the "PRIVATE_KEY" environment variable to set a key.')
}

const batcher = new BatchEncoder(PRIVATE_KEY)
const publicKey = signer.getPublicKey(PRIVATE_KEY)

const batch = (txnList, expectedSigner) => {
  const txns = TransactionList.decode(txnList).transactions
  const headers = txns.map(txn => TransactionHeader.decode(txn.header))

  headers.forEach(header => {
    if (header.batcherPubkey !== publicKey) {
      throw new Error(`Transactions must set batcherPubkey to '${publicKey}'`)
    }
    if (header.signerPubkey !== expectedSigner) {
      throw new Error('Authorized user must have the same key as the signer')
    }
  })

  return batcher.create(txns)
}

module.exports = {
  batch
}
