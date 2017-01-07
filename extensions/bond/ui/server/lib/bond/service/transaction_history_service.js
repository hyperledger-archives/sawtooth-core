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

var r = require('rethinkdb');
var _ = require('underscore');

var block = require('../../sawtooth/model/block');
var {mergeAsset} = require('./holding_service');
var {pagingQuery, pagingResult} = require('./service_utils');


const _receiptByFirm = (firmId) =>
    r.and(r.row('object-type').eq('receipt'),
          r.row('payee-id').eq(firmId));

const _filterReceiptsForFirm = (firmId, currentBlock) =>
    currentBlock.filter(_receiptByFirm(firmId))
        .orderBy(r.desc('timestamp'));

const _mergeReceipt = (currentBlock) => (receipt) => ({
    'bond': currentBlock.get(receipt('bond-id')),
    'payee': currentBlock.get(receipt('payee-id'))('name'),
});

const _fetchReceipts = (firmId, opts) => (currentBlock) =>
    pagingQuery(_filterReceiptsForFirm(firmId, currentBlock)
                     .merge(_mergeReceipt(currentBlock)),
                opts);

const _countReceipts = (firmId) => (currentBlock) =>
    _filterReceiptsForFirm(firmId, currentBlock).count();

const _fetchReceiptsByFirmId = (firmId, opts = {}) =>
    Promise.all([block.current().advancedQuery(_fetchReceipts(firmId, opts), true),
                 block.current().advancedQuery(_countReceipts(firmId))])
           .then(([data, count]) => pagingResult({ count, data }, opts));


const _settlementByFirm = (firmId) =>
    r.and(r.row('object-type').eq('settlement'),
          r.or(r.row('quoting-firm-id').eq(firmId),
               r.row('ordering-firm-id').eq(firmId)));

const _filterSettlementsForFirm = (firmId, currentBlock) =>
    currentBlock.filter(_settlementByFirm(firmId));

const _mergeHolding = (currentBlock, obj, idField) =>
    currentBlock.get(obj(idField)).merge(mergeAsset(currentBlock));

const _mergeSettlement = (currentBlock) => (settlement) => ({
    'quoting-firm': currentBlock.get(settlement('quoting-firm-id'))('name'),
    'ordering-firm': currentBlock.get(settlement('quoting-firm-id'))('name'),
    'order-bond-holding': _mergeHolding(currentBlock, settlement, 'order-bond-holding-id'),
    'order-currency-holding': _mergeHolding(currentBlock, settlement, 'order-currency-holding-id'),
    'quote-bond-holding': _mergeHolding(currentBlock, settlement, 'quote-bond-holding-id'),
    'quote-currency-holding': _mergeHolding(currentBlock, settlement, 'quote-currency-holding-id')
});

const _fetchSettlements = (firmId, opts) => (currentBlock) =>
    pagingQuery(_filterSettlementsForFirm(firmId, currentBlock)
                    .merge(_mergeSettlement(currentBlock)),
                opts);

const _countSettlements = (firmId) => (currentBlock) =>
    _filterSettlementsForFirm(firmId, currentBlock).count();

const _fetchSettlementsByFirmId = (firmId, opts = {}) =>
    Promise.all([block.current().advancedQuery(_fetchSettlements(firmId, opts), true),
                 block.current().advancedQuery(_countSettlements(firmId))])
           .then(([data, count]) => pagingResult({data, count}, opts));

module.exports = {
    receiptsByFirmId: _fetchReceiptsByFirmId,
    settlementsByFirmId: _fetchSettlementsByFirmId,
};

