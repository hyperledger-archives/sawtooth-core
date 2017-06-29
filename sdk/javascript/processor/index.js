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
  TpRegisterRequest,
  TpRegisterResponse,
  TpUnregisterRequest,
  TpProcessRequest,
  TpProcessResponse,
  TpPingResponse,
  TransactionHeader,
  Message
} = require('../protobuf')

const {
  InternalError,
  InvalidTransaction,
  ValidatorConnectionError
} = require('./exceptions')

const State = require('./state')

const {Stream} = require('../messaging/stream')

class TransactionProcessor {
  constructor (url) {
    this._stream = new Stream(url)
    this._handlers = []
  }

  addHandler (handler) {
    this._handlers.push(handler)
  }

  start () {
    this._stream.connect(() => {
      this._stream.onReceive(message => {
        if (message.messageType !== Message.MessageType.TP_PROCESS_REQUEST) {
          if (message.messageType === Message.MessageType.TP_PING) {
            console.log(`Received TpPing`)
            let pingResponse = TpPingResponse.create({status: TpPingResponse.Status.OK})
            this._stream.sendBack(Message.MessageType.TP_PING_RESPONSE,
                                  message.correlationId,
                                  TpPingResponse.encode(pingResponse).finish())
            return
          }
          console.log(`Ignoring ${Message.MessageType.stringValue(message.messageType)}`)
          return
        }

        const request = TpProcessRequest.toObject(TpProcessRequest.decode(message.content), {defaults: false})
        const state = new State(this._stream, request.contextId)

        if (this._handlers.length > 0) {
          let txnHeader = TransactionHeader.decode(request.header)

          let handler = this._handlers.find((candidate) =>
             candidate.transactionFamilyName === txnHeader.familyName &&
               candidate.version === txnHeader.familyVersion &&
               candidate.encoding === txnHeader.payloadEncoding)

          if (handler) {
            handler.apply(request, state)
              .then(() => TpProcessResponse.encode({
                status: TpProcessResponse.Status.OK
              }).finish())
              .catch((e) => {
                if (e instanceof InvalidTransaction) {
                  console.log(e)
                  return TpProcessResponse.create({
                    status: TpProcessResponse.Status.INVALID_TRANSACTION,
                    message: e.message,
                    extendedData: e.extendedData
                  })
                } else if (e instanceof InternalError) {
                  console.log('Internal Error Occurred', e)
                  return TpProcessResponse.create({
                    status: TpProcessResponse.Status.INTERNAL_ERROR,
                    message: e.message,
                    extendedData: e.extendedData
                  })
                } else if (e instanceof ValidatorConnectionError) {
                  console.log('Validator disconnected.  Ignoring.')
                } else {
                  console.log('Unhandled exception, returning INTERNAL_ERROR', e)
                  return TpProcessResponse.create({
                    status: TpProcessResponse.Status.INTERNAL_ERROR,
                    message: `Unhandled exception in ${txnHeader.familyName} ${txnHeader.familyVersion}`
                  })
                }
              })
              .then((response) => {
                if (response) {
                  this._stream.sendBack(Message.MessageType.TP_PROCESS_RESPONSE,
                                        message.correlationId,
                                        TpProcessResponse.encode(response).finish())
                }
              })
              .catch((e) => console.log('Unhandled error on sendBack', e))
          }
        }
      })

      this._handlers.forEach(handler => {
        this._stream.send(
          Message.MessageType.TP_REGISTER_REQUEST,
          TpRegisterRequest.encode({
            family: handler.transactionFamilyName,
            version: handler.version,
            encoding: handler.encoding,
            namespaces: handler.namespaces
          }).finish()
        )
        .then(content => TpRegisterResponse.decode(content))
        .then(ack => {
          let {transactionFamilyName: familyName, version, encoding} = handler
          let status = ack.status === 0 ? 'succeeded' : 'failed'
          console.log(`Registration of [${familyName} ${version} ${encoding}] ${status}`)
        })
        .catch(e => {
          let {transactionFamilyName: familyName, version, encoding} = handler
          console.log(`Registration of [${familyName} ${version} ${encoding}] Failed!`, e)
        })
      })
    })

    process.on('SIGINT', () => this._handleShutdown())
    process.on('SIGTERM', () => this._handleShutdown())
  }

  _handleShutdown () {
    console.log('Unregistering transaction processor')
    this._stream.send(Message.MessageType.TP_UNREGISTER_REQUEST,
                      TpUnregisterRequest.encode().finish())
    process.exit()
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
    throw new Error('apply(TpProcessRequest, state) not implemented')
  }
}

module.exports = {
  TransactionProcessor,
  TransactionHandler
}
