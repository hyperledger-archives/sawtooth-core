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

const {TransactionHandler} = require('sawtooth-sdk/processor')
const {TransactionHeader} = require('sawtooth-sdk/protobuf')
const {InvalidTransaction, InternalError} = require('sawtooth-sdk/processor/exceptions')

const crypto = require('crypto')

const _hash = (x) =>
  crypto.createHash('sha512').update(x).digest('hex').toLowerCase()

const XO_FAMILY = 'xo'
const XO_NAMESPACE = _hash(XO_FAMILY).substring(0, 6)

const VALID_ACTIONS = ['create', 'take']
const VALID_STATES = ['P1-NEXT', 'P2-NEXT', 'P1-WIN', 'P2-WIN', 'TIE']

const _decodeTxnPayload = (payload) =>
  new Promise((resolve, reject) => {
    payload = payload.toString().split(',')
    if (payload.length == 3){
      resolve({
        action: payload[0],
        name: payload[1],
        space: payload[2],
      });
    }
    else {
      let reason = new InvalidTransaction('Invalid payload serialization')
      reject(reason)
    }
  })

const _decodeStateData = (data, name) => {
  let stringData = data.toString()

  if (!stringData) {
    return {
      board: '',
      gameState: '',
      player1: '',
      player2: '',
      addressData: {},
    }
  }

  let addressData = JSON.parse(stringData)

  let gameInfo = addressData[name].split(',')

  return {
    board: gameInfo[0],
    gameState: gameInfo[1],
    player1: gameInfo[2],
    player2: gameInfo[3],
    addressData: addressData,
  }
}

const _setEntry = (state, address, data) => {
  let entries = {
    [address]: data
  }
  return state.set(entries)
}

class XOHandler extends TransactionHandler {
  constructor () {
    super(XO_FAMILY, '1.0', 'csv-utf8', [XO_NAMESPACE])
  }

  apply (transactionProcessRequest, state) {
    return _decodeTxnPayload(transactionProcessRequest.payload)
      .catch(_toInternalError)
      .then((update) => {
        let header = TransactionHeader.decode(transactionProcessRequest.header)
        let player = header.signerPubkey
        if (!update.name) {
          throw new InvalidTransaction('Name is required')
        }

        if (!update.action) {
          throw new InvalidTransaction('Action is required')
        }

        // Perform the action
        const handlerFns = {
          'create': _handleCreate,
          'take': _handleTake,
        }

        const action = update.action
        let handlerFn

        if (VALID_ACTIONS.includes(action)) {
          handlerFn = handlerFns[action]
        } else {
          throw new InvalidTransaction(`Action must be "create" or "take" not ${action}`)
        }

        let address = XO_NAMESPACE + _hash(update.name).slice(-64)

        return state.get([address]).then(handlerFn(state, address, update, player))
          .then((addresses) => {
            if (addresses.length === 0) {
              throw new InternalError('State Error!')
            }
          })
      })
  }

}

const _handleCreate = (state, address, update, player) => (possibleAddressValues) => {
  let stateValueRep = possibleAddressValues[address]

  let stateValue = _decodeStateData(stateValueRep, update.name)
  if (stateValue.board != "") {
    throw new InvalidTransaction("Invalid Action: Game already exists.")
  }

  let board = "---------"
  let gameState = "P1-NEXT"
  let player1 = ""
  let player2 = ""

  let addressData = stateValue.addressData

  addressData[update.name] = [board, gameState, player1, player2].join()

  let setValue = Buffer.from(
    JSON.stringify(addressData).replace(
      /":"/g, '": "'))

  _display(`Player ${player.toString().substring(0, 6)} created a game.`)

  return _setEntry(state, address, setValue)
}

const _handleTake = (state, address, update, player) => (possibleAddressValues) => {
  let stateValueRep = possibleAddressValues[address]
  let stateValue = _decodeStateData(stateValueRep, update.name)

  try{
    let space = parseInt(update.space)
  }
  catch (err) {
    throw new InvalidTransaction("Space could not be converted as an integer.")
  }

  if (update.space < 1 || update.space > 9){
    throw new InvalidTransaction("Invalid space " + update.space)
  }

  if (stateValue.board == "") {
    throw new InvalidTransaction("Invalid Action: Take requires an existing game.")
  }
  if (['P1-WIN', 'P2-WIN', 'TIE'].includes(stateValue.gameState)){
    throw new InvalidTransaction("Invalid Action: Game has ended.")
  }

  if (!(['P1-NEXT', 'P2-NEXT'].includes(stateValue.gameState))) {
    throw new InternalError(`Game has reached an invalid state: ${stateValue.gameState}`)
  }

  if (stateValue.player1 === "") {
    stateValue.player1 = player
  }

  else if (stateValue.player2 === "") {
      stateValue.player2 = player
  }
  let boardList = stateValue.board.split("")

  if (boardList[update.space - 1] != "-") {
    throw new InvalidTransaction("Invalid Action: Space already taken.")
  }

  if (stateValue.gameState === "P1-NEXT" && player == stateValue.player1) {
    boardList[update.space - 1] = 'X'
    stateValue.gameState = "P2-NEXT"
  }
  else if (stateValue.gameState === "P2-NEXT" && player == stateValue.player2) {
    boardList[update.space - 1] = 'O'
    stateValue.gameState = "P1-NEXT"
  }
  else {
    throw new InvalidTransaction(`Not this player's turn: ${player.toString().substring(0, 6)}`)
  }

  stateValue.board = boardList.join("")

  const x_wins = _isWin(stateValue.board, 'X')
  const o_wins = _isWin(stateValue.board, 'O')

  if (x_wins && o_wins) {
    throw new InternalError('Two winners')
  }
  else if (x_wins) {
    stateValue.gameState = "P1-WIN"
  }
  else if (o_wins) {
    stateValue.gameState = "P2-WIN"
  }
  else if (stateValue.board.search('-') == -1) {
    stateValue.gameState = "TIE"
  }

  let name = update.name
  let addressData = stateValue.addressData
  let board = stateValue.board
  let gameState = stateValue.gameState
  let player1 = stateValue.player1
  let player2 = stateValue.player2

  addressData[update.name] = [board, gameState, player1, player2].join()

  let setValue = Buffer.from(
    JSON.stringify(addressData).replace(
      /":"/g, '": "'))

  _display(`Player ${player.toString().substring(0, 6)} takes space: ${update.space}\n\n` +
           _gameToStr(stateValue.board, stateValue.gameState, stateValue.player1
             , stateValue.player2, update.name))

  return _setEntry(state, address, setValue)
}

const _toInternalError = (err) => {
  let message = (err.message) ? err.message : err
  throw new InternalError(message)
}

const _isWin = (board, letter) => {
    let wins = [[1, 2, 3], [4, 5, 6], [7, 8, 9],
            [1, 4, 7], [2, 5, 8], [3, 6, 9],
            [1, 5, 9], [3, 5, 7]]
    let win
    for (let i=0; i < wins.length; i++) {
        win = wins[i]
        if (board[win[0] - 1] === letter
            && board[win[1] - 1] === letter
            && board[win[2] - 1] === letter) {
              return true
            }
        }
    return false
}

const _gameToStr = (board, state, player1, player2, name) => {
    board = board.replace(/-/g, " ")
    board = board.split("")
    let out = ""
    out += `GAME: ${name}\n`
    out += `PLAYER 1: ${player1.substring(0,6)}\n`
    out += `PLAYER 2: ${player2.substring(0,6)}\n`
    out += `STATE: ${state}\n`
    out += `\n`
    out += `${board[0]} | ${board[1]} | ${board[2]} \n`
    out += `---|---|--- \n`
    out += `${board[3]} | ${board[4]} | ${board[5]} \n`
    out += `---|---|--- \n`
    out += `${board[6]} | ${board[7]} | ${board[8]} \n`
    return out
}

const _display = (msg) => {
    let n = msg.search(`\n`)
    let length = 0
    let line_lengths = []
    if (n != -1) {
        msg = msg.split("\n")
        for (let i=0; i < msg.length; i++){
          if (msg[i].length > length) {
            length = msg[i].length
          }
        }
      }
    else {
        length = msg.length
        msg = [msg]
      }

    console.log("+" + "-".repeat(length + 2) + "+")
    for (let i=0; i < msg.length; i++){
        let len = length - msg[i].length

        if ((len%2) == 1){
          console.log("+ " + " ".repeat(Math.floor(len/2)) + msg[i] +
                      " ".repeat(Math.floor(len/2+1))+ " +")
        }
        else{
          console.log("+ " + " ".repeat(Math.floor(len/2)) + msg[i] +
                      " ".repeat(Math.floor(len/2))+ " +")
          }
      }
    console.log("+" + "-".repeat(length + 2) + "+")
}

module.exports = XOHandler
