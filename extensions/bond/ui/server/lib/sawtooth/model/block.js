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

var _ = require('underscore');
var r = require('rethinkdb');
var connector = require('./db_connector');
var utils = require('./utils');
const {cacheFn} = require('../cache_manager');

var _debug = (msg) => (v) => console.log(msg, v) || v;

var _currentBlock = cacheFn(() =>
        connector.exec((db) => db.table('chain_info')
                                 .get('currentblock')
                                 .do((block) => r.branch(block, block, {blockid: '0', blocknum: 0}))));

var _onBlockTable = (currentBlock, f) =>
    currentBlock.then(block => connector.exec(db => f(db.table('blk' + block.blockid), db)));

var _projectionFields = (fields) =>
    _.contains(fields, 'id') ? fields : ['id'].concat(fields);

var _scopeToCurrentBlock = (currentBlock) => ({

    info: () => currentBlock,

    entry: (id) => _onBlockTable(currentBlock, (block) => block.get(id)),

    entries: (ids, asArray) =>
        _onBlockTable(currentBlock, (block) => block.getAll(r.args(ids)))
            .then(utils.cursorToArray(asArray)),

    findFirst: (query) =>
        _onBlockTable(currentBlock, (block) => block.filter(query).limit(1).coerceTo('array'))
            .then(_.first),

    findExact: (query, opts) => {
        opts = !_.isUndefined(opts) ? opts : {};
        return _onBlockTable(currentBlock, utils.findWithOpts(query, opts))
            .then(utils.cursorToArray(opts.asArray));
    },

    advancedQuery: (queryFn, asArray) =>
        _onBlockTable(currentBlock, queryFn).then(utils.cursorToArray(asArray)),

    count: (query) =>_onBlockTable(currentBlock,
            block => query ?  block.filter(query).count() : block.count()),

    projection: (query, fields, asArray) =>
        _onBlockTable(currentBlock, block => block.filter(query).pluck(_projectionFields(fields)))
            .then(utils.cursorToArray(asArray)),


});

module.exports = {
    current: () => _scopeToCurrentBlock(_currentBlock()),
};
