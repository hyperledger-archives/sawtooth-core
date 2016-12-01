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
'use strict';

try {
    require('longjohn');
} catch (e) {}
var compression          = require('compression');
var fs                   = require('fs');
var winston              = require('winston');
var flash                = require('connect-flash');
var express              = require('express');
var bondRoutes           = require('./lib/bond/routes');
var sawtoothRoutes       = require('./lib/sawtooth/routes');
var updateService        = require('./lib/sawtooth/service/update_service');
var bodyParser           = require('body-parser');
var cookieParser         = require('cookie-parser');

var ledgerService        = require('./lib/sawtooth/service/ledger_service');

var logger = require('./lib/sawtooth/logger').getSyncLogger();

// Configure app
var app = express();
app.use('/',express.static('../client/resources/public'));

app.use(bodyParser.json());
app.use(cookieParser());

app.use(function(req, res, next) {
    res.header("Access-Control-Allow-Origin", "*");
    res.header("Access-Control-Allow-Headers",
               "Origin, X-Requested-With, Content-Type, Accept, participant-id");
    next();
});

bondRoutes.configure(app);
sawtoothRoutes.configure(app);

// These ensure that the the transactions are submitted to
// the validator correctly
ledgerService.setFloatFields(['CouponRate', 'Amount']);

var port = parseInt(process.env.PORT || "3000");

var server = app.listen(port,'0.0.0.0', function () {
    var host = server.address().address;
    var port = server.address().port;

    logger.info('Explorer is listening at http://%s:%s', host, port);
});

updateService.init(server);


//--------  COMPRESSION TEST  ----------

//Express/connect
app.use(compression()); //compress all requests
