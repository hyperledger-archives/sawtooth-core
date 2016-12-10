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
/**
 * Created by staite on 11/22/2015.
 */
"use strict";
var winston = require('winston');
var path    = require ('path');

module.exports = {
    getRESTLogger : getRESTLogger,
    getSyncLogger : getSyncLogger
};

var _transports = (targetName) => {
    var fileTransport = 
            new (winston.transports.DailyRotateFile)({
                filename: path.join(__dirname,'..','..', "log", targetName + '.log'),
                name: targetName,
                colorize: true,
                zippedArchive: true,
                datePattern: '.yyyy-MM-ddTHH'});
    if (process.env.NODE_ENV !== 'test') {
        return [new (winston.transports.Console)()];
    } else {
        // We're going to ignore logs in the test environment;
        return [ fileTransport ];
    }
};

function getRESTLogger() {
    return  new (winston.Logger)({
        transports: _transports('rest')
    });
    
}

function getSyncLogger() {
    return  new (winston.Logger)({
        transports: _transports('sync')
    });
}
