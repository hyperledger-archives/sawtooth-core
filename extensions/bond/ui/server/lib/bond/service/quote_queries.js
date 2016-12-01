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

const r = require('rethinkdb');
const {pendingTransactions} = require('./service_utils');

const _pendingQuotesXForm = (txn, update) => ({
    'id': update('ObjectId'),
    'object-id': update('ObjectId'),
    'update-id': txn('id'),
    'pending': true,
    'creator-id': txn('creator-id'),
    'firm': update('Firm'),
    'cusip': update('Cusip'),
    'isin': update('Isin'),
    'ask-price': update('AskPrice'),
    'ask-qty': update('AskQty'),
    'bid-price': update('BidPrice'),
    'bid-qty': update('BidQty'),
    'timestamp': r.now().toEpochTime(),
    'status': 'Pending Commit',
});

const _queryQuotesForBond = (bond, block, db = null, optionalParticipantId = null) => {
    let cusip = typeof bond === 'string' ? bond : bond('cusip');
    let isin = typeof bond === 'string' ? bond : bond('isin');
    
    let baseQuery = block.filter({'object-type': 'quote', 'status': 'Open'});

    if (db && optionalParticipantId) {
        baseQuery = pendingTransactions(db, optionalParticipantId, 'CreateQuote', _pendingQuotesXForm)
                        .union(baseQuery);
    } 

    return baseQuery.filter((obj) =>
        r.and(r.or(obj.hasFields('cusip').and(obj('cusip').eq(cusip)),
                   obj.hasFields('isin').and(obj('isin').eq(isin)))));
};

module.exports = {
    quotesForBondQuery: _queryQuotesForBond,
};

