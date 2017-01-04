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

const {
  TransactionProcessorRegisterRequest,
  // Acknowledgement,
  TransactionProcessRequest,
  TransactionProcessResponse,
  TransactionHeader
} = require('../protobuf')

const {InternalError, InvalidTransaction} = require('./exceptions')

const {Stream} = require('../client/stream')

const State = require('../client/state')

class TransactionProcessor {
  constructor (url) {
    this._stream = new Stream(url)
    this._handlers = []
  }

  addHandler (handler) {
    this._handlers.push(handler)
  }

  start () {
    this._stream.connect()

    this._stream.onReceive(message => {
      console.log('Received', message.messageType)

      const request = TransactionProcessRequest.decode(message.content)

      const state = new State(this._stream, request.contextId)

      if (this._handlers.length > 0) {
        let txnHeader = TransactionHeader.decode(request.header)

        let handler = this._handlers.find((candidate) =>
           candidate.transactionFamilyName === txnHeader.familyName &&
             candidate.version === txnHeader.familyVersion &&
             candidate.encoding === txnHeader.payloadEncoding)

        if (handler) {
          handler.apply(request, state)
            .then(() => TransactionProcessResponse.encode({
              status: TransactionProcessResponse.Status.OK
            }).finish())
            .catch((e) => {
              if (e instanceof InvalidTransaction) {
                console.log(e)
                return TransactionProcessResponse.encode({
                  status: TransactionProcessResponse.Status.INVALID_TRANSACTION
                }).finish()
              } else if (e instanceof InternalError) {
                console.log(e)
                return TransactionProcessResponse.encode({
                  status: TransactionProcessResponse.Status.INTERNAL_ERROR
                }).finish()
              } else {
                console.log('Unhandled exception, returning INTERNAL_ERROR')
                console.log(e)
                return TransactionProcessResponse.encode({
                  status: TransactionProcessResponse.Status.INTERNAL_ERROR
                }).finish()
              }
            })
            .then((response) =>
                  this._stream.sendBack('tp/response', message.correlationId, response))
        }
      }
    })

    this._handlers.forEach(handler => {
      this._stream.send(
        'tp/register',
        TransactionProcessorRegisterRequest.encode({
          family: handler.transactionFamilyName,
          version: handler.version,
          encoding: handler.encoding,
          namespaces: handler.namespaces
        }).finish()
      )
      /*
      .then(content => Acknowledgement.decode(content))
      .then(ack => {
        let {transactionFamilyName: familyName, version, encoding} = handler
        let status = ack.status === 0 ? 'Succeded' : 'Failed'
        console.log(`Registration of [${familyName} ${version} ${encoding}] ${status}`)
      })
     */
    })
  }
}

const _readOnlyProperty = (instance, propertyName, value) =>
    Object.defineProperty(instance, propertyName, {
      writeable: false,
      enumerable: true,
      congigurable: true,
      value})

class TransactionHandler {
  constructor (transactionFamilyName, version, encoding, namespaces) {
    _readOnlyProperty(this, 'transactionFamilyName', transactionFamilyName)
    _readOnlyProperty(this, 'version', version)
    _readOnlyProperty(this, 'encoding', encoding)
    _readOnlyProperty(this, 'namespaces', namespaces)
  }

  apply (transactionProcessRequest, state) {
    throw new Error('apply(transactionProcessRequest, state) not implemented')
  }
}

module.exports = {
  TransactionProcessor,
  TransactionHandler
}
