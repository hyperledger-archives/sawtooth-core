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

"use strict";

var r = require('rethinkdb');
var util = require('util');

var connector = require('./db_connector');


var _withState = (f, onDone) => (state) =>
    f(state.db, state.dbName)
        .run(state.conn)
        .then((res) => onDone(res, state.dbName))
        .then(() => state);

var _createDbIfNotExists = _withState(
        (db, dbName) =>
            r.dbList().contains(dbName)
             .do((dbExists) => r.branch(dbExists, {dbs_created: 0}, r.dbCreate(dbName))),
        (res, dbName) => {
            if(res.dbs_created > 0) {
                console.log(util.format("DB '%s' was created", dbName));
            } else {
                console.log(util.format("DB '%s' exists", dbName));
            }
        });

var _createTableIfNotExists = (table) => _withState(
        (db) => db.tableList().contains(table)
                  .do((tableExists) => r.branch(tableExists, {tables_created: 0}, db.tableCreate(table))),
        (res) => {
            if(res.tables_created > 0) {
                console.log(util.format("Table '%s' was created", table));
            } else {
                console.log(util.format("Table '%s' exists", table));
            }
        });

var _insertIfNotExists = (table, records) => _withState(
        (db) => db.table(table)
                  .insert(records),
        (res) => {
            if (res.inserted > 0) {
                console.log(util.format("Inserted %d into '%s'",res.inserted, table));
            }
        });

var _indexIfNotExists = (table, index) => _withState(
        (db) => db.table(table).indexList().contains(index)
                  .do(indexExists => r.branch(indexExists, {created: 0}, db.table(table).indexCreate(index))),
        (res) => {
            if(res.created > 0) {
                console.log(util.format("Index '%s' on '%s' was created", index, table));
            } else {
                console.log(util.format("Index '%s' on '%s' exists", index, table));
            }
        });


let bootstrap = (connector) =>
    connector.connect()
    .then(_createDbIfNotExists)
    .then(_createTableIfNotExists('transactions'))
    .then(_indexIfNotExists('transactions', 'created'))
    .then(_indexIfNotExists('transactions', 'Nonce'))
    .then(_createTableIfNotExists('block_list'))
    .then(_createTableIfNotExists('txn_list'))
    .then(_indexIfNotExists('txn_list', 'Nonce'))
    .then(_createTableIfNotExists('chain_info'))
    .then(_insertIfNotExists('chain_info', {
        id: 'currentblock',
        blockid: "0",
        blocknum: 0
    }))
    .then(_createTableIfNotExists('blk0'));

module.exports = bootstrap;
