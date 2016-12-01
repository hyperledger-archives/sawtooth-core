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
 * Sawtooth Routes module.
 *
 * @module sawtooth/routes
 */

'use strict';

const _ = require('underscore');
const express = require('express');

const ledgerService = require('./service/ledger_service');
const block = require('./model/block');

const logger = require('./logger').getRESTLogger();

const _intParam = (param, defaultValue) => {
   if(_.isUndefined(param)) {
       return defaultValue;
   }

   try {
       return parseInt(param);
   } catch (e) {
       return defaultValue;
   }
};

const _queryOptions = (requestQuery) => ({
    limit: _intParam(requestQuery.limit),
    page: _intParam(requestQuery.page)
});

const _send500 = (res) => (e) => {
    logger.error(e);
    res.status(500).send();
};

const _simplePromiseHandler = (f) => (req, res) =>
    f(req).then(result => res.send(result))
          .catch(_send500(res));

const _notImplemented = (req, res) => res.status(501).send('Not Implemented');

module.exports = {
    /**
     * Configures the given express app with routes for general ledger
     * activities, which will be available under  `/api/ledger`.  Currently this includes:
     *
     * * `/chain` - returns the current block info (id, number and size)
     * * `/transactions` - A GET returns the list of transactions, a POST will take a signed
     * transaction and submit it to a sawtooth validator
     * * `/transactions/:transactionId` - a GET returns a complete transaction
     *
     * @param {express.Application|express.Router} app - the app to configure
     *
     * @static
     */
    configure: (app) => {

        var ledgerApiRouter = express.Router();

        ledgerApiRouter.route('/chain')
            .get((req, res) =>
                    Promise.all([block.current().info(),
                                 block.current().count()])
                        .then(([info, count]) =>
                            res.send(_.chain(info)
                                      .assign({size: count})
                                      .omit('id')
                                      .value())));

        ledgerApiRouter.route('/transactions')
            .get(_simplePromiseHandler((req) =>
                        ledgerService.all(_queryOptions(req.query))))
            .post(_simplePromiseHandler((req) => {
                var txn = req.body.transaction;
                var annotations = req.body.annotations;
                return ledgerService.createTransaction(txn, annotations);
            }));

        var transactionsRouter = express.Router({mergeParams: true});
        ledgerApiRouter.use('/transactions/:transactionId', transactionsRouter);

        transactionsRouter.route('')
            .get((req, res) =>
                    ledgerService.get(req.params.transactionId)
                        .then(txn => {
                            if (txn) {
                                res.send(txn);
                            } else {
                                res.status(404).send();
                            }
                        })
                        .catch(_send500(res)));


        app.use('/api/ledger', ledgerApiRouter);
    },

    /**
     * Utility for for pulling out common optins from the request for
     * query operations.
     *
     * @param {Object} requestQuery  - param object from the request
     * @returns {Object} - an object containing `limit` and `page`,
     * both of which may be null.
     *
     * @method
     * @static
     */
    queryOptions: _queryOptions,

    /**
     * Utility method for returning a 500 error.  Useful when used in a
     * `catch` promise handler.
     *
     * @param {express.Response} res - the response
     *
     * @method
     * @static
     */
    send500: _send500,

    /**
     * Handler for a 501 response
     *
     * @param {express.Request} req - the request
     * @param {express.Response} res - the reponse
     *
     * @method
     * @static
     */
    notImplemented: _notImplemented,

    /**
     * Integer parsing with defaults.
     *
     * @param {string} param - the param to parse
     * @param {Number} [defaultValue] - the default value if the param is empty
     * or parsing fails.
     * @returns {Number} - the resulting int value
     *
     * @method
     * @static
     */
    intParam: _intParam,

    /**
     * A basic promise handler.  Given a function that returns a promise, it will send
     * the result to the response, or a 500 error if any unexpected errors occur.
     * @param {Function} f - f(req): Promise
     *
     * @method
     * @static
     */
    simplePromiseHandler: _simplePromiseHandler,
};
