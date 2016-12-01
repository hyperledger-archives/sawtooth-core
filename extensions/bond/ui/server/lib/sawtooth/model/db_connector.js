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

var logger = require('../logger').getRESTLogger();
var r = require('rethinkdb');
var util = require('util');

const cacheManager = require('../cache_manager');
const {List: IList, Map: IMap} = require('immutable');

var _onReconnect = IList();
var _state = IMap();

var DEFAULT_DB_HOST = 'localhost';
var DEFAULT_DB_PORT = '28015';
var DEFAULT_DB_NAME = 'bond';


function _closeConnection() {
    if(!_state.isEmpty()) {
        let oldState = _state;
        _state = IMap();
        oldState.get("conn").close()
            .then(() => {
                logger.info('DB connection closed.');
            })
            .catch((e) => {
                logger.error("Error on closing db connection");
                logger.error(e);
            });
    }
}

function monitorConnection(conn) {
    conn.on('error', function (e) {
        logger.warn(e);
        logger.warn("DB connection error.  Closing connection.");
        _closeConnection();
    });

    conn.on('timeout', function() {
        logger.warn("DB connection timeout.  Closing connection.");
        _closeConnection();
    });

    conn.on('close', () => {
        logger.warn("DB connection closed. Cleaning up.");
        _state = IMap();
    });
}

const _nextTick = (f) => setTimeout(f, 0);

const onReconnect = (f) =>
    _onReconnect = _onReconnect.push(f);

const doReconnect = () =>
    _onReconnect.forEach(f => _nextTick(f));

function connect(){
    if (_state.isEmpty()) {
        var host = process.env.DB_HOST || DEFAULT_DB_HOST;
        var port = parseInt(process.env.DB_PORT || DEFAULT_DB_PORT);
        var dbName = process.env.DB_NAME || DEFAULT_DB_NAME;

        logger.info(util.format(
                    "Connecting to DB  %s:%d/%s",
                    host, port, dbName));

        cacheManager.clearCaches();
        return r.connect({host, port})
                .then(function (conn) {
                    _state = IMap({
                        conn,
                        db: r.db(dbName),
                        dbName,
                    });

                    monitorConnection(conn);
                    _nextTick(doReconnect);
                    return _state.toJS();
                })
                .catch(function (e) {
                    logger.error(util.format("Unable to connect to %s:%d/%s",
                                             host, port, dbName));
                    throw e;
                });
    } else{
        return Promise.resolve(_state.toJS());
    }
}

var makeQuery = (f) => connect().then(state => f(state.db));

var exec = (f) => connect().then(state =>
        f(state.db).run(state.conn)
            .catch(e => {
                if(e.name === "ReqlDriverError" &&
                        /^Could not connect.*/.match(e.msg)) {
                    _closeConnection();
                }
                throw e;
            }));

module.exports = {
    connect,
    makeQuery,
    thenMakeQuery: (f) => () => makeQuery(f),
    exec: exec,
    thenExec: (f) => () => exec(f),
    shutdown: _closeConnection,
    onReconnect,
    currentState: () => _state,
};
