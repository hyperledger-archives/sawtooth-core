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
var connector = require('../../sawtooth/model/db_connector');

const {TransactionStatuses} = require('../../sawtooth/constants');
var {pagingQuery, pagingResult, pendingTransactions} = require('./service_utils');


const _isPending = (order, db) =>
    db.table('transactions').filter(txn =>
        r.and(txn('Status').eq(TransactionStatuses.PENDING),
            txn('Updates')(0)('OrderId').eq(order('id'))))
    .count().gt(0);

const _getBond = (currentBlock, order, idField) =>
    currentBlock.filter(o => o('object-type').eq('bond').and(o(idField).eq(order(idField))))
                .coerceTo('array')
                .do((res) => r.branch(res.isEmpty(), null, res.nth(0)));

const _merge = (currentBlock) => order => ({
    bond: r.branch(order.hasFields('isin'),
                   _getBond(currentBlock, order, 'isin'),
                   _getBond(currentBlock, order, 'cusip')),
    trader: currentBlock.get(order('creator-id'))('username'),
});

let _pendingTxnXform = (txn, update) => ({
    'update-id': txn('id'),
    'pending': true,
    'id': update('ObjectId'),
    'object-type': 'order',
    'object-id': update('ObjectId'),
    'creator-id':txn('creator-id'),
    'isin': update('Isin'),
    'cusip': update('Cusip'),
    'firm-id': update('FirmId'),
    'quote-id': update('QuoteId'),
    'timestamp': r.now().toEpochTime(),
    'quantity': update('Quantity'),
    'order-type': update('OrderType'),
    'limit-price': update('LimitPrice'),
    'limit-yeild': update('LimitYeild'),
    'action': update('Action'),
    'status': 'Pending Commit',
});

const _filterOrders = (participantId, opts, currentBlock, db) => {
    let query = pendingTransactions(db, participantId, 'CreateOrder', _pendingTxnXform)
                    .union(currentBlock.filter({'object-type': 'order'}));

    if (opts.creatorOnly) {
        query = query.filter(r.row('creator-id').eq(participantId));
    }

    return query;
};

const _fetchOrders = (participantId, opts) => (currentBlock, db) => {
    let query = pagingQuery(_filterOrders(participantId, opts, currentBlock, db), opts);

    if (opts.checkPending) {
        query = query.merge(order => ({pending: _isPending(order, db)}));
    }

    return query.merge(_merge(currentBlock))
                .coerceTo('array');
};

const _countOrders = (participantId, opts) => (currentBlock, db) =>
    _filterOrders(participantId, opts, currentBlock, db).count();

module.exports = {
    orders: (optionalParicipantId, opts = {}) =>
        Promise.all([block.current().advancedQuery(_fetchOrders(optionalParicipantId, opts)),
                     block.current().advancedQuery(_countOrders(optionalParicipantId, opts))])
            .then(([data, count]) => pagingResult({data, count}, opts))
};
