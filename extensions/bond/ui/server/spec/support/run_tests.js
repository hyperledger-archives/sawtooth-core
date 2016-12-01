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
process.env.NODE_ENV = 'test';
try {
    require('longjohn');
} catch (e) {}

var Jasmine = require('jasmine');
var SpecReporter = require('jasmine-spec-reporter');
var jasmine = new Jasmine();

var util = require('util');
var r = require('rethinkdb');
var connector = require('../../lib/sawtooth/model/db_connector');
var bootstrap = require('../../lib/sawtooth/model/bootstrap');

// Let's override the Mongo DB location for the tests
var TEST_DB_NAME = 'bond_test';

process.env.DB_NAME = TEST_DB_NAME;

jasmine.loadConfigFile('spec/support/jasmine.json');
jasmine.addReporter(new SpecReporter({
    displaySpecDuration: true,
}));

var _cleanup = () =>
    connector.exec(() => r.dbDrop(TEST_DB_NAME))
        .then(() => connector.shutdown())
        .catch(e => console.log(e));

jasmine.onComplete((passed) => {
    console.log(util.format("Dropping test db '%s'", TEST_DB_NAME));

    _cleanup();
});

process.on('SIGINT', _cleanup).on('SIGTERM', _cleanup);

var _createDbIfNotExists = (dbName) => (state) => 
    r.dbList().contains(dbName)
       .do(dbExists =>
            r.branch(dbExists, {dbs_created: 0}, r.dbCreate(dbName)))
        .run(state.conn);

var _createIfNotExists = (table) => (db) =>
    db.tableList().contains(table).do((tableExists) =>
            r.branch(tableExists, {tables_created: 0}, db.tableCreate(table)));

var _indexIfNotExists = (table, index) => (db) =>
    db.table(table).indexList().contains(index).do((exists) =>
            r.branch(exists, {created: 0}, db.table(table).indexCreate(index)));

console.log(util.format("Creating test db '%s'...", TEST_DB_NAME));

bootstrap(connector)
    .then(() => console.log("Database created") || true)
    .catch(err => console.log("Unable to create database!", err) || false)
    .then((dbWasCreated) =>
            dbWasCreated ? jasmine.execute() : console.error("Tests Aborted"))
    .catch((err) => console.log("Test Error!\n", err));

