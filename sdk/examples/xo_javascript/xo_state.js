/**
 * Copyright 2018 Intel Corporation
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

const crypto = require('crypto')

class XoState {
  constructor (context) {
    this.context = context
    this.addressCache = new Map([])
    this.timeout = 500 // Timeout in milliseconds
  }

  getGame (name) {
    return this._loadGames(name).then((games) => games.get(name))
  }

  setGame (name, game) {
    let address = _makeXoAddress(name)

    return this._loadGames(name).then((games) => {
      games.set(name, game)
      return games
    }).then((games) => {
      let data = _serialize(games)

      this.addressCache.set(address, data)
      let entries = {
        [address]: data
      }
      return this.context.setState(entries, this.timeout)
    })
  }

  deleteGame (name) {
    let address = _makeXoAddress(name)
    return this._loadGames(name).then((games) => {
      games.delete(name)

      if (games.size === 0) {
        this.addressCache.set(address, null)
        return this.context.deleteState([address], this.timeout)
      } else {
        let data = _serialize(games)
        this.addressCache.set(address, data)
        let entries = {
          [address]: data
        }
        return this.context.setState(entries, this.timeout)
      }
    })
  }

  _loadGames (name) {
    let address = _makeXoAddress(name)
    if (this.addressCache.has(address)) {
      if (this.addressCache.get(address) === null) {
        return Promise.resolve(new Map([]))
      } else {
        return Promise.resolve(_deserialize(this.addressCache.get(address)))
      }
    } else {
      return this.context.getState([address], this.timeout)
        .then((addressValues) => {
          if (!addressValues[address].toString()) {
            this.addressCache.set(address, null)
            return new Map([])
          } else {
            let data = addressValues[address].toString()
            this.addressCache.set(address, data)
            return _deserialize(data)
          }
        })
    }
  }
}

const _hash = (x) =>
  crypto.createHash('sha512').update(x).digest('hex').toLowerCase().substring(0, 64)

const XO_FAMILY = 'xo'

const XO_NAMESPACE = _hash(XO_FAMILY).substring(0, 6)

const _makeXoAddress = (x) => XO_NAMESPACE + _hash(x)

module.exports = {
  XO_NAMESPACE,
  XO_FAMILY,
  XoState
}

const _deserialize = (data) => {
  let gamesIterable = data.split('|').map(x => x.split(','))
    .map(x => [x[0], {name: x[0], board: x[1], state: x[2], player1: x[3], player2: x[4]}])
  return new Map(gamesIterable)
}

const _serialize = (games) => {
  let gameStrs = []
  for (let nameGame of games) {
    let name = nameGame[0]
    let game = nameGame[1]
    gameStrs.push([name, game.board, game.state, game.player1, game.player2].join(','))
  }

  gameStrs.sort()

  return Buffer.from(gameStrs.join('|'))
}
