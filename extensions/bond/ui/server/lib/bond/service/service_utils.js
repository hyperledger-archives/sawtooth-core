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
const r = require('rethinkdb');

var {TransactionStatuses} = require('../../sawtooth/constants');

let _onFirst = (query, f) =>
    query.limit(1)
         .coerceTo('array')
         .do((res) => r.branch(res.isEmpty(), null, f(res.nth(0))));

let _first = query => _onFirst(query, _.identity);

let _firstField = (query, field) => _onFirst(query, first => first(field));

let _updateField = (txn, field) =>
    r.branch(txn('Updates').nth(0).hasFields(field),
             txn('Updates').nth(0)(field),
             null);

module.exports = {
    pagingQuery: (initialQuery, opts = {}) => {
        let query = initialQuery;

        if (!_.isUndefined(opts.limit) &&
               !_.isUndefined(opts.page) && opts.page > 0) {
            query = query.skip(opts.limit * opts.page);
        }

        if (!_.isUndefined(opts.limit)) {
            query = query.limit(opts.limit);
        }

        return query;
    },

    pagingResult: (result, opts = {}) => {
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
    },

    pendingTransactions: (db, participantId, updateType, txnToBlockObjectXform) =>
        db.table('transactions')
          .filter(r.and(r.row('Status').eq(TransactionStatuses.PENDING),
                        r.row('creator-id').eq(participantId),
                        r.row('Updates').nth(0)('UpdateType').eq(updateType)))
          .map((txn) =>
                  txnToBlockObjectXform(txn,  (fieldName) => _updateField(txn, fieldName))),

    first: _first,
    firstField: _firstField,
};

