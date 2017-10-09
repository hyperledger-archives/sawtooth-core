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
const jsSchema = require('js-schema')

const HOST = process.env.DB_HOST || 'localhost'
const PORT = process.env.DB_PORT || 28015
const NAME = process.env.DB_NAME || 'tnt'

// Connection to db for query methods, run connect before querying
let connection = null

const connect = () => {
  return r.connect({host: HOST, port: PORT, db: NAME})
    .then(conn => {
      connection = conn
    })
    .catch(err => {
      console.error(`Unable to connect to "${NAME}" db at ${HOST}:${PORT}}!`)
      console.error(err.message)
    })
}

const runQuery = query => {
  return query
    .run(connection)
    .catch(err => {
      console.error(err.message)
      throw new Error(err.message)
    })
}

const queryWithCurrentBlock = query => {
  return runQuery(
    r.table('blocks')
      .orderBy(r.desc('blockNum'))
      .nth(0)('blockNum')
      .do(query)
  )
}

// Runs a specified query against a database table
const queryTable = (table, query, removeCursor = true) => {
  return query(r.table(table))
    .run(connection)
    .then(cursor => removeCursor ? cursor.toArray() : cursor)
    .catch(err => {
      console.error(`Unable to query "${table}" table!`)
      console.error(err.message)
      throw new Error(err.message)
    })
}

// Use for queries that modify a table, turns error messages into errors
const modifyTable = (table, query) => {
  return queryTable(table, query, false)
    .then(results => {
      if (!results) {
        throw new Error(`Unknown error while attempting to modify "${table}"`)
      }
      if (results.errors > 0) {
        throw new Error(results.first_error)
      }
      return results
    })
}

// Inserts a document into a table, throwing an error on failure
// Accepts an optional validator function, which should have an errors method
const insertTable = (table, doc) => {
  return modifyTable(table, t => t.insert(doc))
    .then(results => {
      if (results.inserted === 0) {
        throw new Error(`Unknown Error: Unable to insert to ${table}`)
      }
      return results
    })
}

const updateTable = (table, primary, changes) => {
  return modifyTable(table, t => {
    return t.get(primary).update(changes, {returnChanges: true})
  })
    .then(results => {
      if (results.replaced === 0 && results.unchanged === 0) {
        throw new Error(`Unknown Error: Unable to update ${primary}`)
      }
      return results
    })
}

// Validates a db input based on a schema as promised
const validate = (input, schema) => {
  return Promise.resolve()
    .then(() => {
      const validator = jsSchema(schema)
      if (validator(input)) return input

      const errors = validator.errors(input)
      if (!errors) throw new Error('Invalid Input: one or more keys forbidden')

      const [ key, message ] = _.entries(errors)[0]
      throw new Error(`Invalid Input: "${key}" - ${message}`)
    })
}

module.exports = {
  connect,
  runQuery,
  queryWithCurrentBlock,
  queryTable,
  modifyTable,
  insertTable,
  updateTable,
  validate
}
