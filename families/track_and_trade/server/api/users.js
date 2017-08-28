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
const db = require('../db')
const { BadRequest, InternalServerError } = require('./errors')

const isValidCreate = schema({
  username: String,
  password: String,
  email: /.+@.+\..+/,
  publicKey: String,
  privateKey: String,
  '*': null
})

const create = user => {
  if (!isValidCreate(user)) {
    const errors = isValidCreate.errors(user)
    const firstKey = Object.keys(errors)[0]
    throw new BadRequest(`User Invalid: "${firstKey}" - ${errors[firstKey]}`)
  }

  return db.insertUsers(user)
    .then(results => {
      if (results.errors) {
        throw new BadRequest(results.first_error)
      }

      if (results.inserted === 0) {
        throw new InternalServerError('Unknown error while creating user')
      }

      return user
    })
}

module.exports = {
  create
}
