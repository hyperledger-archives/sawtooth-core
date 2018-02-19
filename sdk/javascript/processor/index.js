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
  PingResponse,
  Message
} = require('../protobuf')

const {
  InternalError,
  AuthorizationException,
  InvalidTransaction,
  ValidatorConnectionError
} = require('./exceptions')

const Context = require('./context')

const { Stream } = require('../messaging/stream')

/**
 * TransactionProcessor is a generic class for communicating with a
 * validator and routing transaction processing requests to a
 * registered handler. It uses ZMQ and channels to handle requests
 * concurrently.
 *
 * @param {string} url - the URL of the validator
 */
class TransactionProcessor {
  constructor (url) {
    this._stream = new Stream(url)
    this._handlers = []
  }

  /**
   * addHandler adds the given handler to the transaction processor so
   * it can receive transaction processing requests. All handlers must
   * be added prior to starting the processor.
   *
   * @param {TransactionHandler} handler - a handler to be added
   */
  addHandler (handler) {
    this._handlers.push(handler)
  }

  /**
   * start connects the transaction processor to a validator and
   * starts listening for requests and routing them to an appropriate
   * handler.
   */
  start () {
    this._stream.connect(() => {
      this._stream.onReceive(message => {
        if (message.messageType !== Message.MessageType.TP_PROCESS_REQUEST) {
          if (message.messageType === Message.MessageType.PING_REQUEST) {
            console.log(`Received Ping`)
            let pingResponse = PingResponse.create()
            this._stream.sendBack(
              Message.MessageType.PING_RESPONSE,
              message.correlationId,
              PingResponse.encode(pingResponse).finish()
            )
            return
          }
          console.log(
            `Ignoring ${Message.MessageType.stringValue(message.messageType)}`
          )
          return
        }

        const request = TpProcessRequest.toObject(
          TpProcessRequest.decode(message.content),
          { defaults: false }
        )
        const context = new Context(this._stream, request.contextId)

        if (this._handlers.length > 0) {
          let txnHeader = request.header

          let handler = this._handlers.find(
            (candidate) =>
              candidate.transactionFamilyName === txnHeader.familyName &&
              candidate.versions.includes(txnHeader.familyVersion))

          if (handler) {
            let applyPromise
            try {
              applyPromise = Promise.resolve(handler.apply(request, context))
            } catch(err) {
              applyPromise = Promise.reject(err)
            }
            applyPromise
            .then(() =>
              TpProcessResponse.create({
                status: TpProcessResponse.Status.OK
              })
            )
            .catch(e => {
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
              } else if (e instanceof AuthorizationException) {
                console.log(e)
                return TpProcessResponse.create({
                  status: TpProcessResponse.Status.INVALID_TRANSACTION,
                  message: e.message,
                  extendedData: e.extendedData
                })
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
                this._stream.sendBack(
                  Message.MessageType.TP_PROCESS_RESPONSE,
                  message.correlationId,
                  TpProcessResponse.encode(response).finish()
                )
              }
            })
            .catch(e => console.log('Unhandled error on sendBack', e))
          }
        }
      })

      this._handlers.forEach(handler => {
        handler.versions.forEach(version => {
          this._stream.send(
            Message.MessageType.TP_REGISTER_REQUEST,
            TpRegisterRequest.encode({
              family: handler.transactionFamilyName,
              version: version,
              namespaces: handler.namespaces
            }).finish())
            .then(content => TpRegisterResponse.decode(content))
            .then(ack => {
              let { transactionFamilyName: familyName } = handler
              let status =
                ack.status === TpRegisterResponse.Status.OK
                  ? 'succeeded'
                  : 'failed'
              console.log(
                `Registration of [${familyName} ${version}] ${status}`
              )
            })
            .catch(e => {
              let { transactionFamilyName: familyName } = handler
              console.log(
                `Registration of [${familyName} ${version}] Failed!`,
                e
              )
            })
        })
      })
    })

    process.on('SIGINT', () => this._handleShutdown())
    process.on('SIGTERM', () => this._handleShutdown())
  }

  _handleShutdown () {
    console.log('Unregistering transaction processor')
    this._stream.send(
      Message.MessageType.TP_UNREGISTER_REQUEST,
      TpUnregisterRequest.encode().finish()
    )
    process.exit()
  }
}

module.exports = {
  TransactionProcessor
}
