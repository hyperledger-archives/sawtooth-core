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
var connector = require('../../sawtooth/model/db_connector');
var {pagingQuery, pagingResult} = require('./service_utils');


const _mergeAsset = (currentBlock) => (holding) => ({
    asset: currentBlock.get(holding('asset-id')),
});

const _filterHoldingsForFirm = (firmId, currentBlock) =>
    currentBlock.filter(r.and(r.row('object-type').eq('holding'),
                              r.row('owner-id').eq(firmId)));

const _fetchHoldings = (firmId, opts) => (currentBlock) =>
    pagingQuery(_filterHoldingsForFirm(firmId, currentBlock)
                     .merge(_mergeAsset(currentBlock)),
                opts);


const _countHoldings = (firmId) => (currentBlock) =>
    _filterHoldingsForFirm(firmId, currentBlock).count();

const _fetchHoldingsByFirmId = (firmId, opts = {}) =>
    Promise.all([block.current().advancedQuery(_fetchHoldings(firmId, opts), true),
                 block.current().advancedQuery(_countHoldings(firmId))])
           .then(([data, count]) => pagingResult({ count, data }));

module.exports = {
    holdingsByFirmId: _fetchHoldingsByFirmId,
    mergeAsset: _mergeAsset,
};
