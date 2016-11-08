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
var participantService = require('./service/participant_service');
var exchangeService = require('./service/exchange_service');
var offerService = require('./service/offer_service');
var assetService = require('./service/asset_service');

var logger = require('../sawtooth/logger').getRESTLogger();


var _notImplemented = (req, res) => res.status(501).send('Not Implemented');

let _queryOptions = (requestQuery) => _.assign(
        routes.queryOptions(requestQuery),
        {
            filter: {
                participantId: requestQuery.participantId,
                assetId: requestQuery.assetId,
                holdingId: requestQuery.holdingId,
                inputAssetId: requestQuery.inputAssetId,
                outputAssetId: requestQuery.outputAssetId,
            },
        });

module.exports = {
    configure: (app) => {

        var mktplaceApiRouter = express.Router();

        mktplaceApiRouter.route('/participants')
            .get(routes.simplePromiseHandler((req) =>
                        participantService.getUsersNameAndIds()))
            .post(routes.simplePromiseHandler((req) =>
                        participantService.getByAddress(req.body.address)));

        var participantRouter = express.Router({mergeParams: true});

        mktplaceApiRouter.use('/participants/:participantId', participantRouter);

        // Handles returning the participant details
        participantRouter.route('')
             .get((req, res) => 
                participantService.participant(req.params.participantId)
                    .then(participant => {
                        if (participant) {
                            res.send(participant);
                        } else {
                            res.status(404).send();
                        }
                    })
                    .catch(routes.send500(res)));

        // Returns a participant's historic exchanges
        participantRouter.route('/exchanges')
             .get(routes.simplePromiseHandler((req) =>
                  exchangeService.historicTransactions(req.params.participantId,
                                                       _queryOptions(req.query))));

        // Returns a participant's offers
        participantRouter.route('/offers')
            .get(routes.simplePromiseHandler((req) =>
                    offerService.offers(req.params.participantId,
                                        _queryOptions(req.query))));

        // Operations on a participant's offer
        participantRouter.route('/offers/:offerId')
            .get(routes.simplePromiseHandler((req) =>
                    offerService.offer(req.params.participantId,
                                       req.params.offerId)))
            .post((req, res) => {
                if(!req.body.action) {
                    res.status(400).send("Missing 'action'. Must be one of ['revoke']");
                    return;
                }

                if(req.body.action !== 'revoke') {
                    res.status(400).send("The parameter 'action' must be one of ['revoke']");
                    return;
                }

                offerService.revokeOffer(req.params.participantId,
                                         req.params.offerId)
                    .then(result => res.send(result))
                    .catch(routes.send500(res));
            });


        // Returns offer's which are actionable by the given participant
        participantRouter.route('/actionable_offers')
            .get(routes.simplePromiseHandler((req) =>
                    offerService.availableOffers(req.params.participantId,
                                                 _queryOptions(req.query))));


        // All historic transactions, and transaction creation
        mktplaceApiRouter.route('/exchanges')
            .get(routes.simplePromiseHandler((req) => 
                  exchangeService.historicTransactions(null,
                                                       _queryOptions(req.query))));

        // Offer Creation
        mktplaceApiRouter.route('/offers')
            .get(_notImplemented)
            .post(routes.simplePromiseHandler((req) =>
                offerService.createOffer(req.body)));

        // Assest
        mktplaceApiRouter.route('/assets')
            .get(routes.simplePromiseHandler((req) =>
                        Promise.all([assetService.assets(), assetService.assetTypes()])
                            .then(_.spread((assets, assetTypes) => ({
                                assets,
                                assetTypes
                            })))))
            .post(_notImplemented);

        app.use('/api/mktplace', mktplaceApiRouter);
    },
};
