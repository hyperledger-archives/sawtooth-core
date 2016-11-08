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

var helpers = require('../../support/helpers');

var connector = require('../../../lib/sawtooth/model/db_connector');
var transaction = require('../../../lib/sawtooth/model/transaction');
var consts = require('../../../lib/sawtooth/constants');



describe('Transaction Paging', () => {

    beforeEach((done) => {
        connector.exec(db => db.table('txn_list').insert(
                            helpers.generateExchanges(10, consts.TransactionStatuses.FAILED)))
            .then(done)
            .catch(helpers.failAsync(done));
    });

    afterEach((done) => {
        connector.exec(db => db.table('txn_list').delete())
            .then(done)
            .catch(helpers.failAsync(done));
    });

    it('should limit the number to the page size', (done) => {
        transaction.findExact({}, {asArray: true, limit: 3, page: 0})
            .then(txns => {
                expect(txns.length).toBe(3);
                expect(_.pluck(txns, 'id')).toEqual(jasmine.arrayContaining([
                    '10009',
                    '10008',
                    '10007',
                ]));
            })
            .then(done)
            .catch(helpers.failAsync(done));
    });

    it('should skip to the next page', (done) => {
        transaction.findExact({}, {asArray: true, limit: 3, page: 1})
            .then(txns => {
                expect(txns.length).toBe(3);
                expect(_.pluck(txns, 'id')).toEqual(jasmine.arrayContaining([
                    '10006',
                    '10005',
                    '10004',
                ]));
            })
            .then(done)
            .catch(helpers.failAsync(done));
    });

    it('should return only the availble items on the last page', (done) => {
        transaction.findExact({}, {asArray: true, limit: 3, page: 3})
            .then(txns => {
                expect(txns.length).toBe(1);
                expect(_.pluck(txns, 'id')).toEqual(jasmine.arrayContaining([
                    '10000',
                ]));
            })
            .then(done)
            .catch(helpers.failAsync(done));

    });

    it('should return nothing if it has paged too far', (done) => {
        transaction.findExact({}, {asArray: true, limit: 3, page: 5})
            .then(txns => {
                expect(txns).toEqual([]);
            })
            .then(done)
            .catch(helpers.failAsync(done));
    });

});
