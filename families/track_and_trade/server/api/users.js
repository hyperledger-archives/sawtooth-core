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

const _ = require('lodash')
const db = require('../db/users')
const agents = require('../db/agents')
const auth = require('./auth')
const { BadRequest } = require('./errors')

const create = user => {
  return Promise.resolve()
    .then(() => {
      return agents.fetch(user.publicKey, null)
        .catch(() => {
          throw new BadRequest('Public key must match an Agent on blockchain')
        })
    })
    .then(() => auth.hashPassword(user.password))
    .then(hashed => {
      return db.insert(_.assign({}, user, {password: hashed}))
        .catch(err => { throw new BadRequest(err.message) })
    })
    .then(() => auth.createToken(user.publicKey))
    .then(token => ({
      authorization: token,
      encryptedKey: user.encryptedKey || null
    }))
}

const update = (changes, { authedKey }) => {
  return Promise.resolve()
    .then(() => {
      if (changes.password) {
        return auth.hashPassword(changes.password)
          .then(hashed => _.set(changes, 'password', hashed))
      }
      return changes
    })
    .then(finalChanges => db.update(authedKey, finalChanges))
    .then(updated => _.omit(updated, 'password'))
}

module.exports = {
  create,
  update
}
