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

const schema = require('js-schema')
const db = require('./')

const validator = schema({
  username: String,
  password: String,
  email: /.+@.+\..+/,
  publicKey: String,
  '?encryptedKey': String,
  '*': null
})

const query = query => db.queryTable('users', query)

const insert = user => {
  return db.insertTable('users', user, validator)
    .then(results => {
      return db.insertTable('usernames', {username: user.username})
        .then(() => results)
        .catch(err => {
          // Delete user, before re-throwing error
          return db.queryTable('users', users => {
            return users.get(user.publicKey).delete()
          }, false)
            .then(() => { throw new Error(err) })
        })
    })
}

module.exports = {
  query,
  insert
}
