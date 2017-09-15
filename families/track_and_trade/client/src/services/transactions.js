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

const m = require('mithril')
const sjcl = require('sjcl')
const { signer, TransactionEncoder } = require('sawtooth-sdk/client')
const modals = require('../components/modals')
const api = require('../services/api')

const STORAGE_KEY = 'tnt.encryptedKey'

let txnEncoder = null
const encoderSettings = {
  familyName: 'track_and_trade',
  familyVersion: '1.0',
  payloadEncoding: 'application/protobuf',
  inputs: ['1c1108'],
  outputs: ['1c1108'],
  batcherPubkey: null
}

api.get('info')
  .then(res => { encoderSettings.batcherPubkey = res.pubkey })

const requestPassword = () => {
  let password = null

  return modals.show(modals.BasicModal, {
    title: 'Enter Password',
    acceptText: 'Submit',
    body: m('.container', [
      m('.mb-4', 'Please confirm your password to decrypt your signing key.'),
      m('input.form-control', {
        type: 'password',
        oninput: m.withAttr('value', value => { password = value })
      })
    ])
  })
    .then(() => password)
}

/**
 * Generates a new private key, saving it it to memory and storage (encrypted).
 * Returns both a public key and the encrypted private key.
 */
const makePrivateKey = password => {
  const privateKey = signer.makePrivateKey()
  txnEncoder = new TransactionEncoder(privateKey, encoderSettings)

  const encryptedKey = sjcl.encrypt(password, privateKey)
  localStorage.setItem(STORAGE_KEY, encryptedKey)

  const publicKey = signer.getPublicKey(privateKey)
  return { encryptedKey, publicKey }
}

/**
 * Saves an encrypted key to storage, and the decrypted version in memory.
 */
const setPrivateKey = (password, encryptedKey) => {
  const privateKey = sjcl.decrypt(password, encryptedKey)
  txnEncoder = new TransactionEncoder(privateKey, encoderSettings)

  localStorage.setItem(STORAGE_KEY, encryptedKey)

  return encryptedKey
}

/**
 * Clears the users private key from memory and storage.
 */
const clearPrivateKey = () => {
  const encryptedKey = localStorage.getItem(STORAGE_KEY)

  localStorage.clearItem(STORAGE_KEY)
  txnEncoder = null

  return encryptedKey
}

/**
 * Wraps a Protobuf payload in a TransactionList and submits it to the API.
 * Prompts user for their password if their private key is not in memory.
 */
const submit = payload => {
  return Promise.resolve()
    .then(() => {
      if (txnEncoder) return

      return requestPassword()
        .then(password => {
          const encryptedKey = localStorage.getItem(STORAGE_KEY)
          setPrivateKey(encryptedKey, password)
        })
    })
    .then(() => {
      const txnList = txnEncoder.createEncoded(payload)
      return api.postBinary('transactions', txnList)
    })
}

module.exports = {
  makePrivateKey,
  setPrivateKey,
  clearPrivateKey,
  submit
}
