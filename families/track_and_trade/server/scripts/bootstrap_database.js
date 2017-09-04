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

r.connect({host: HOST, port: PORT})
  .then(conn => {
    console.log(`Creating "${NAME}" database...`)
    r.dbList().contains(NAME).run(conn)
      .then(dbExists => {
        if (dbExists) throw new Error(`"${NAME}" already exists`)
        return r.dbCreate(NAME).run(conn)
      })
      .then(() => {
        console.log('Creating "users" table...')
        return r.db(NAME).tableCreate('users', {
          primaryKey: 'publicKey'
        }).run(conn)
      })
      .then(() => {
        // The usernames table is used to quickly ensure unique usernames
        console.log('Creating "usernames" table...')
        return r.db(NAME).tableCreate('usernames', {
          primaryKey: 'username'
        }).run(conn)
      })
      .then(() => {
        console.log('Creating "blocks" table...')
        return r.db(NAME).tableCreate('blocks', {
          primaryKey: 'blockNum'
        }).run(conn)
      })
      .then(() => {
        console.log('Creating and populating "state" table...')
        return r.db(NAME).tableCreate('state').run(conn)
      })
      .then(() => {
        return r.db(NAME).table('state').insert({
          name: 'message',
          value: 'Hello Track and Trade!'
        }).run(conn)
      })
      .then(() => {
        console.log('Bootstrapping complete, closing connection.')
        return conn.close()
      })
      .catch(err => {
        console.log(`Unable to bootstrap "${NAME}" db: ${err.message}`)
        return conn.close()
      })
  })
  .catch(err => {
    console.log(`Unable to connect to db at ${HOST}:${PORT}}: ${err.message}`)
  })
