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

var _ = require('underscore');
require('../../sawtooth/mixins');

var {UpdateTypes} = require('../constants');
var {TransactionStatuses} = require('../../sawtooth/constants');
var connector = require('../../sawtooth/model/db_connector');
var block = require('../../sawtooth/model/block');
var transaction = require('../../sawtooth/model/transaction');

var r = require('rethinkdb');
var queries = require('../../sawtooth/model/queries');

const {getHolding} = require('./service_common');

var _update = txn => txn('Updates').nth(0);

var _executeQuery = (participantId, subquery, opts) =>
    block.current().info().then(info => connector.exec(db => {
        var currentBlock = db.table('blk' + info.blockid);

        var _mergeHolding = (o, field) =>
            r.branch(o.hasFields(field),
                     getHolding(currentBlock, o(field)),
                     null);

        var _txnsAsOffers = 
                db.table('transactions')
                  .filter(
                    r.and(_update(r.row)('UpdateType').eq(UpdateTypes.REGISTER_SELL_OFFER),
                          r.row('Status').eq(TransactionStatuses.PENDING),
                          r.row('creator').eq(participantId)))
            .map((txn) => ({
                id: txn('id'),
                pending: true,
                creator: r.branch(txn.hasFields('creator'), txn('creator'), null),
                name: _update(txn)('Name'),
                description: _update(txn)('Description'),
                input: _update(txn)('InputId'),
                output: _update(txn)('OutputId'),
                ratio: _update(txn)('Ratio'),
                minimum: _update(txn)('Minimum'),
                maximum: _update(txn)('Maximum'),
                execution: _update(txn)('Execution'),
                'execution-state': {
                    'ParticipantList': []
                },
                'object-type': 'SellOffer',
            }));

        var _isProcessing = (offer) =>
                db.table('transactions')
                  .filter(t => r.and(t('Status').eq(TransactionStatuses.PENDING),
                                     t('creator').eq(participantId),
                                     _update(t)('UpdateType').eq(UpdateTypes.EXCHANGE),
                                     _update(t)('OfferIdList').contains(offer('id'))))
                  .count().gt(0);
                        

        var _isUnregistering = (offer) =>
                db.table('transactions')
                  .filter(t => r.and(t('Status').eq(TransactionStatuses.PENDING),
                                     _update(t)('CreatorId').eq(participantId),
                                     _update(t)('UpdateType').eq(UpdateTypes.UNREGISTER_SELL_OFFER),
                                     _update(t)('ObjectId').eq(offer('id'))))
                  .count().gt(0);

        var filter = subquery;
        if(opts.filter.participantId) {
            let participantId = opts.filter.participantId;
            if(participantId[0] === '!') {
                filter = r.and(filter, r.row('creator').eq(participantId.substring(1)).not());
            } else {
                filter = r.and(filter, r.row('creator').eq(participantId));
            }
        }

        var query = _txnsAsOffers
                .union(currentBlock.filter({'object-type': 'SellOffer'}))
                .filter(filter);

        query =
            query.merge(offer => ({
                input: _mergeHolding(offer, 'input'),
                output: _mergeHolding(offer, 'output'),
                processing: _isProcessing(offer),
                revoked: _isUnregistering(offer),
            }))
            .without('execution-state');

        var secondaryFilters = [];
        // filter this first, as it is more specific than assets
        if (opts.filter.holdingId) {
            secondaryFilters.push(r.or(r.row('input')('id').eq(opts.filter.holdingId),
                                       r.row('output')('id').eq(opts.filter.holdingId)));
        } else if (opts.filter.assetId) {
            secondaryFilters.push(r.or(r.row('input')('asset').eq(opts.filter.assetId),
                                       r.row('output')('asset').eq(opts.filter.assetId)));
        } else if (opts.filter.inputAssetId) {
            secondaryFilters.push(r.row('input')('asset').eq(opts.filter.inputAssetId));
        } else if (opts.filter.outputAssetId) {
            secondaryFilters.push(r.row('output')('asset').eq(opts.filter.outputAssetId));
        }

        if (secondaryFilters.length > 0) {
            query = query.filter(r.and(r.args(secondaryFilters)));
        }

        if (opts.count) {
            return query.count();
        }

        if (opts.sort) {
            query = query.orderBy(opts.sort);
        }

        if (opts.limit && opts.page && opts.page > 0) {
            query = query.skip(opts.limit * opts.page);
        }

        if (opts.limit) {
            query = query.limit(opts.limit);
        }        

        return query.coerceTo('array');
    }));

var _defaultOpts = (opts) => _.assign({filter: {}}, opts);

var _countOpts = (opts) => _.chain(opts)
                            .omit('page', 'limit')
                            .assign({count: true})
                            .value();

var _doFetch = (participantId, subquery, opts) => {
    opts = _defaultOpts(opts);
    return Promise.all([_executeQuery(participantId, subquery, _countOpts(opts)),
                        _executeQuery(participantId, subquery, opts)])
        .then(_.spread((count, data) => {
                var result = { count, data };

                if (!_.isUndefined(opts.page) && !_.isUndefined(opts.limit)) {
                    var nextPage = opts.page + 1;
                    if (nextPage * opts.limit <= result.count) {
                        result.nextPage = nextPage;
                        result.hasMore = true;
                    } else {
                        result.hasMore = false;
                    }

                }

                return result;
        }));
};


let _debug = (v) => console.log(v) || v;

module.exports = {

    offer: (participantId, id) =>
        _doFetch(participantId, r.row('id').eq(id), {limit: 1})
            .then(offerResult => _.first(offerResult.data)),
    /**
     * Returns all committed, open offers in the system.
     *
     * `creator` is optional
     */
    offers: (creator, options) => _doFetch(creator,
                    creator ? r.row('creator').eq(creator) : null, options),

    /**
     * Returns all available offers for a given participant.
     *
     * `participantId`: id of the participant
     */
    availableOffers: (participantId, options) =>
        _doFetch(
                participantId,
                r.or(r.row('execution').eq('Any'),
                     r.row('execution').eq('ExecuteOnce'),
                     r.and(r.row('execution').eq('ExecuteOncePerParticipant'),
                           r.row('execution-state')('ParticipantList').contains(participantId).not())),
                options),

};
