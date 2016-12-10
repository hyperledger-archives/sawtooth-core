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

var express = require('express');
var _ = require('underscore');
require('../sawtooth/mixins');

var routes = require('../sawtooth/routes');
var block = require('../sawtooth/model/block');
var logger = require('../sawtooth/logger').getRESTLogger();

const participantService = require('./service/participant_service');
const organizationService = require('./service/organization_service');
const orderService = require('./service/order_service');
const quoteService = require('./service/quote_service');
const bondService = require('./service/bond_service');
const holdingService = require('./service/holding_service');
const historyService = require('./service/transaction_history_service');


var _notImplemented = (req, res) => res.status(501).send('Not Implemented');

const _send500 = (res) => (e) => {
    logger.error(e);
    res.status(500).send();
};

const _simplePromiseHandler = (f) => (req, res) =>
    f(req).then(result => res.send(result))
          .catch(_send500(res));

const _queryOptions = (requestQuery) =>
    _.extend(routes.queryOptions(requestQuery), {
        checkPending: requestQuery['check-pending'] == 'true',
        creatorOnly: requestQuery['creator-only'] == 'true',
    });

module.exports = {
    configure: (app) => {

        var bondApiRouter = express.Router();

        bondApiRouter.route('/bonds')
            .get(_simplePromiseHandler(req =>
                        bondService.bonds(req.get('participant-id'),
                                          req.query.search,
                                          _queryOptions(req.query))));

        var bondRouter = express.Router({mergeParams: true});
        bondApiRouter.use('/bonds/:bondId', bondRouter);

        bondRouter.route('')
            .get((req, res) => {
                bondService.bondByBondIdentifier(req.params.bondId)
                    .then((bond) => {
                        if(bond) {
                            res.send(bond);
                        } else {
                            res.status(404).send();
                        }
                    })
                    .catch(_send500(res));
            });

        bondRouter.route('/latest-quote/:pricingSource')
            .get(_simplePromiseHandler(req =>
                    quoteService.latestQuote(req.params.bondId, req.params.pricingSource)));

        bondApiRouter.route('/bond-identifiers')
            .get(_simplePromiseHandler(req =>
                bondService.bondIdentifiers()));

        bondApiRouter.route('/quotes/:bondId')
            .get(_simplePromiseHandler(req =>
                quoteService.bondAndQuotes(req.get('participant-id'),
                                           req.params.bondId,
                                           _queryOptions(req.query))));

        bondApiRouter.route('/orders')
            .get(_simplePromiseHandler(req =>
                        orderService.orders(req.get('participant-id'),
                                            _queryOptions(req.query))));


        bondApiRouter.route('/organizations')
            .get(_simplePromiseHandler(req =>
                organizationService.organizations()));

        var organizationRouter = express.Router({mergeParams: true});
        bondApiRouter.use('/organizations/:orgId', organizationRouter);

        organizationRouter.route('')
            .get((req, res) => {
                organizationService.organizationById(req.params.orgId)
                    .then((bond) => {
                        if(bond) {
                            res.send(bond);
                        } else {
                            res.status(404).send();
                        }
                    })
                    .catch(_send500(res));
            });

        organizationRouter.route('/holdings')
            .get(_simplePromiseHandler(req =>
                    holdingService.holdingsByFirmId(req.params.orgId,
                                                    _queryOptions(req.query))));

        organizationRouter.route('/receipts')
            .get(_simplePromiseHandler(req =>
                    historyService.receiptsByFirmId(req.params.orgId,
                                                    _queryOptions(req.query))));

        organizationRouter.route('/settlements')
            .get(_simplePromiseHandler(req =>
                    historyService.settlementsByFirmId(req.params.orgId,
                                                       _queryOptions(req.query))));

        bondApiRouter.route('/participants/:address')
            .get((req, res) => {
                let fetchFn = req.query['fetch-firm'] ?
                    participantService.participantWithFirm :
                    participantService.participantByAddress;

                return fetchFn(req.params.address)
                .then(participant => {
                    if (participant) {
                        res.send(participant);
                    } else {
                        res.status(404).send();
                    }
                })
                .catch(_send500(res));
            });

        bondApiRouter.route('/participants')
            .get(_simplePromiseHandler(req =>
                participantService
                    .participantNamesAndAddresses(req.query)));

        app.use('/api/bond', bondApiRouter);
    },
};
