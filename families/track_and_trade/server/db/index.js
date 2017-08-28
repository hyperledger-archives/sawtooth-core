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
const queryTable = (table, query) => {
  return query(r.table(table))
    .run(connection)
    .then(cursor => cursor.toArray())
    .catch(err => {
      console.log(`Unable to query "${table}" table!`)
      console.log(err)
    })
}

const queryUsers = query => queryTable('users', query)

const queryState = query => queryTable('state', query)

module.exports = {
  connect,
  queryUsers,
  queryState
}
