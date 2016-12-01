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

var r = require('rethinkdb');
var _ = require('underscore');
var block = require('../../sawtooth/model/block');
var bondService = require('./bond_service');
var {pagingQuery, pagingResult, firstField} = require('./service_utils');
var {quotesForBondQuery} = require('./quote_queries');


const _fetchQuotes = (participantId, bondId, opts ={}) => (block, db) =>
    pagingQuery(quotesForBondQuery(bondId, block, db, participantId)
                    .orderBy(r.desc('bid-price'))
                    .without('id', 'object-id', 'object-type')
                    .merge((quote) => ({
                         'firm-name': firstField(block.filter({'pricing-source': quote('firm')}), 'name'),
                     })),
               opts);

const _countQuotes = (participantId, bondId) => (block, db) =>
    quotesForBondQuery(bondId, block, db, participantId).count();

const query = (qry) => block.current().advancedQuery(qry, true);

const _fetchBondAndQuotes = (participantId, bondId, opts = {}) =>
	Promise.all([bondService.bondByBondIdentifier(bondId),
                 query(_fetchQuotes(participantId, bondId, opts)),
                 query(_countQuotes(participantId, bondId))])
        .then(([bond, data, count]) => ({
            bond,
            quotes: pagingResult({data, count})
        }));

const _fetchLatestQuote = (bondId, pricingSource) => {
    return query(block =>
        quotesForBondQuery(bondId, block)
            .filter(r.row('firm').eq(pricingSource))
            .orderBy(r.desc('timestamp'))
            .limit(1)
            .coerceTo('array'))
        .then(_.first);
};

module.exports = {
    bondAndQuotes: _fetchBondAndQuotes,
    latestQuote: _fetchLatestQuote,
};
