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

const r = require('rethinkdb')
const _ = require('lodash')

const HOST = process.env.DB_HOST || 'localhost'
const PORT = process.env.DB_PORT || 28015
const NAME = process.env.DB_NAME || 'tnt'

// Connection to db for query methods, run connect before querying
let connection = null

const connect = () => {
  r.connect({host: HOST, port: PORT, db: NAME})
    .then(conn => {
      connection = conn
    })
    .catch(err => {
      console.log(`Unable to connect to "${NAME}" db at ${HOST}:${PORT}}!`)
      console.log(err)
    })
}

// Runs a specified query against a database table
const queryTable = (table, query, removeCursor = true) => {
  return query(r.table(table))
    .run(connection)
    .then(cursor => removeCursor ? cursor.toArray() : cursor)
    .catch(err => {
      console.log(`Unable to query "${table}" table!`)
      console.log(err)
    })
}

// Inserts a document into a table, throwing an error on failure
// Accepts an optional validator function, which should have an errors method
const insertTable = (table, doc, validator = d => true) => {
  if (!validator(doc)) {
    const [ key, message ] = _.entries(validator.errors(doc))[0]
    return Promise.reject(new Error(`Invalid Input: "${key}" - ${message}`))
  }

  return queryTable(table, t => t.insert(doc), false)
    .then(results => {
      if (results.errors) {
        throw new Error(results.first_error)
      }
      if (results.inserted === 0) {
        throw new Error(`Unknown Error: Unable to insert to ${table}`)
      }
      return results
    })
}

module.exports = {
  connect,
  queryTable,
  insertTable
}
