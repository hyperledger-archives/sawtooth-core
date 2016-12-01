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

var socket_io = require('socket.io');
var _ = require('underscore');

const cacheManager = require('../cache_manager');
var logger = require('../logger').getRESTLogger();
var connector = require('../model/db_connector');
var block = require('../model/block.js');

var BLOCK_UPDATE_EVENT = 'chain_info';

var _sendInfo = (socket) =>
    block.current().info()
         .then((info) => socket.emit(BLOCK_UPDATE_EVENT,
                    _.omit(info, 'id')));

let _currentCursor = null;

var _monitorBlockChanges = (io) => {
    if(_currentCursor) {
        _currentCursor.close();
        _currentCursor = null;
    }

    return connector.exec(db =>
            db.table('chain_info')
              .changes())
        .then(cursor => {
            _currentCursor = cursor;
            cursor.each((err, change) => {
                if(err) {
                    logger.error("Error on chain_info changes.");
                    logger.error(err);
                    return false;
                }

                cacheManager.clearCaches();

                _sendInfo(io);
            }, () => { _currentCursor = null; });
        });
};

module.exports = {

    init: (server) => {
        var io = socket_io(server);

        io.on('connection', socket => _sendInfo(socket));

        _monitorBlockChanges(io);

        connector.onReconnect(() => _monitorBlockChanges(io));
    }

};
