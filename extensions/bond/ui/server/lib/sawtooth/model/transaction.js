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

const _ = require('underscore');
const schema = require('js-schema');

const r = require('rethinkdb');
const {Map: IMap, fromJS} = require('immutable');

const validation = require('../validation');
const connector = require('./db_connector');
const block = require('./block');
const {asArray, cursorToArray, findWithOpts} = require('./utils');
const {TransactionStatuses} = require('../constants');
const logger = require('../logger').getSyncLogger();

var txnAnnotationSchema = schema({
    'id': String,
    'blockid': String,
    'Status': [TransactionStatuses.PENDING],
    '?creator': [null, String],
    'created': Number,
    '?address': String,
});

let MERGE_FNS = IMap();

const _registerMergeFns = (name, mergeFnSpec) => {
    if (_.isUndefined(mergeFnSpec.transactionFamilyPattern) ||
            _.isUndefined(mergeFnSpec.functions))
    {
        throw new Error("Must specify a transactionFamilyPattern and functions");
    }

    if (!_.isObject(mergeFnSpec.functions)) {
        throw new Error("functions must be a map of transaction types to merge functions");
    }

    MERGE_FNS = MERGE_FNS.set(name, fromJS(mergeFnSpec));
};

var _search = (node, r) => {
    if(!node) {
        return null;
    }

    if(node.data && r.exec(node.data)) {
        return node.data;
    }

    if(node.args && node.args.length > 0) {
        for(var i = 0; i < node.args.length; i++) {
            var res = _search(node.args[i], r);
            if(res) {
                return res;
            }
        }
    }
    return null;
};

var _transactionFilter = (db, f, currentBlock) => {
    return f(db.table("transactions"), currentBlock);
};

var _onTransactions = (opts, f) =>
    block.current().info()
        .then(info => connector.exec(db => {
            let currentBlock = db.table('blk' + info.blockid);

            let txns = db.table('transactions').orderBy({index: r.desc('Nonce')})
                         .filter(r.or(r.row('Status').eq(TransactionStatuses.FAILED),
                                      r.row('Status').eq(TransactionStatuses.PENDING)))

                         .union(db.table('txn_list').orderBy({index: r.desc('Nonce')}));
            let query = f(txns);

            query = MERGE_FNS.valueSeq()
                .map(mergeFnSpec => [_search(query, mergeFnSpec.get('transactionFamilyPattern')),
                                     mergeFnSpec.get('functions')])
                .map(([updateType, functions]) => functions.get(updateType))
                .filter(f => !_.isNull(f) && _.isFunction(f))
                .reduce((query, fn) => query.merge(fn(currentBlock)), query);

            if(opts.secondaryQuery) {
                query = query.filter(opts.secondaryQuery);
            }

            if (opts.count) {
                return query.count();
            }


            if (opts.limit && opts.page && opts.page > 0) {
                query = query.skip(opts.limit * opts.page);
            }

            if (opts.limit) {
                query = query.limit(opts.limit);
            }        

            return query;
        }));

var _transactionQuery = (query, opts) => {
    opts = !_.isUndefined(opts) ? opts : {};
    return _onTransactions(opts, transactions => transactions.filter(query))
            .then(cursorToArray(opts.asArray));
};


var _applyDefaults = (transaction) =>
    _.extend({
        'Status': TransactionStatuses.PENDING,
        'creator': null,
        'created': Date.now()
    }, transaction);

module.exports = {
    schema: txnAnnotationSchema,

    registerMergeFns: _registerMergeFns,

    get: (id) => _transactionQuery({id: id}, {asArray: true, limit: 1}).then(_.first),

    all: (opts) => _transactionQuery({}, opts),

    findExact: (query, opts) => _transactionQuery(query, opts),

    count: (query, opts) => _transactionQuery(query, _.assign({count: true}, opts)),

    insert: (transaction) => {
        transaction = _applyDefaults(transaction);
        return validation.validate(txnAnnotationSchema, transaction,
                'Unable to insert transaction: Invalid Value')
            .then(() => connector.exec(db => db.table('transactions')
                                               .insert(transaction)));
    },

    transactionFilter: _transactionFilter,
            
};
