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

// models
var r = require('rethinkdb');
var queries = require('../../sawtooth/model/queries');
var transaction = require('../../sawtooth/model/transaction');
var block = require('../../sawtooth/model/block');

var participantService = require('./participant_service');

var {TRANSACTION_TYPE, UpdateTypes} = require('../constants');
var {TransactionStatuses} = require('../../sawtooth/constants');
var utils = require('../utils');

var logger = require('../../sawtooth/logger').getRESTLogger();

var _update = txn => txn('Updates').nth(0);

var _blockItem = (txn, fieldName, currentBlock) => 
    r.branch(_update(txn).hasFields(fieldName),
             currentBlock.get(_update(txn)(fieldName)),
             null);

var _blockItems = (txn, fieldName, currentBlock) =>
    r.branch(r.and(_update(txn).hasFields(fieldName),
                   _update(txn)(fieldName).isEmpty().not()),
            currentBlock.getAll(r.args(_update(txn)(fieldName))).coerceTo('array'),
            []);

var _MERGE_FNS = {};

_MERGE_FNS[UpdateTypes.EXCHANGE] = (currentBlock) => 
        (txn) => ({
            sellOffers: _blockItems(txn, 'OfferIdList', currentBlock),
            input: _blockItem(txn, 'InitialLiabilityId', currentBlock),
            output: _blockItem(txn, 'FinalLiabilityId', currentBlock)
        });

_MERGE_FNS[UpdateTypes.REGISTER_SELL_OFFER] = (currentBlock) =>
        (txn) => ({
            input: _blockItem(txn, 'InputId', currentBlock),
            output: _blockItem(txn, 'OutputId', currentBlock),
        });
    
transaction.registerMergeFns(TRANSACTION_TYPE, {
    transactionFamilyPattern: /\/mktplace.+/,
    functions: _MERGE_FNS
});

var _applyDetails = (txn) => {
    var sellOffer = _.first(txn.sellOffers);
    var amount = sellOffer ?
        Math.round(txn.Updates[0].InitialCount / utils.toFraction(sellOffer.ratio).denominator) :
        0;
    return _.extend(_.clone(txn.Updates[0]), {
        id: txn.id,
        status: txn.Status,
        creator: txn.creator,
        sellOffer: sellOffer,
        input: txn.input,
        output: txn.output,
        amount: amount,
        created: txn.created,
        pending: txn.Status === TransactionStatuses.PENDING,
        failed: txn.Status === TransactionStatuses.FAILED,
    });
};

var _defaultOpts = (opts) => _.assign({filter: {}}, opts);

var _countOpts = (opts) => _.chain(opts)
                            .omit('page', 'limit')
                            .value();

var _service = {

    historicTransactions: (optionalCreatorId, options) => {
        options = _defaultOpts(options);
        let statuses = [
            TransactionStatuses.COMMITTED,
            TransactionStatuses.FAILED
        ];

        let ands = [
            queries.$in('Status', statuses),
            _update(r.row)('UpdateType').eq(UpdateTypes.EXCHANGE),
        ];

        if(optionalCreatorId) {
            ands.push(r.row('creator').eq(optionalCreatorId));
        } else {
            ands.push(_update(r.row)('OfferIdList').isEmpty().not());
        }

        let query = r.and(r.args(ands));

        var findOptions = {
            page: options.page,
            limit: options.limit,
            asArray: true,
        };

        // filter holding first, as it is more specific
        if(options.filter.holdingId) {
            findOptions.secondaryQuery = r.or(r.row('input')('id').eq(options.filter.holdingId),
                                              r.row('output')('id').eq(options.filter.holdingId),
                                              r.row('id').eq(options.filter.holdingId));
        } else if (options.filter.assetId) {
            findOptions.secondaryQuery = r.or(r.row('input')('asset').eq(options.filter.assetId),
                                              r.row('output')('asset').eq(options.filter.assetId),
                                              r.row('id').eq(options.filter.assetId));
        }

        return Promise.all([transaction.count(query, _countOpts(findOptions)),
                            transaction.findExact(query, findOptions)]) 
            .then(_.spread((count, txns) => ({
                count,
                data: _.map(txns, _applyDetails)
            })));
    },    

};

module.exports = _service;
