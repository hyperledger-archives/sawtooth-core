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
var exchangeService = require('../../../lib/mktplace/service/exchange_service');
var transaction = require('../../../lib/sawtooth/model/transaction');
var consts = require('../../../lib/sawtooth/constants');

describe('ExchangeService with paging', () => {
        
    beforeEach((done) => {
        connector.exec(db => db.table('txn_list').insert(
                            helpers.generateExchanges(10, consts.TransactionStatuses.COMMITTED)))
            .then(() => helpers.createBlock('523242', [
                        {
                            "id" : "70afa6a11ed3bb45",
                            "creator" : "4f2ede53e0e08e6f",
                            "description" : "Currency asset type",
                            "name" : "/asset-type/currency",
                            "object-type" : "AssetType",
                            "restricted" : true,
                            "fqname" : "//immxleague/asset-type/currency"
                        },
                        {
                            "id" : "50d3dc7b9bed498c",
                            "creator" : "4f2ede53e0e08e6f",
                            "description" : "Team stock asset type",
                            "name" : "/asset-type/teamstock",
                            "object-type" : "AssetType",
                            "restricted" : true,
                            "fqname" : "//immxleague/asset-type/teamstock"
                        }
            ]))
            .then(done)
            .catch(helpers.failAsync(done));
    });

    afterEach((done) => {
        connector.exec(db => db.table('txn_list').delete())
            .then(() => helpers.cleanBlock('523242'))
            .then(done)
            .catch(helpers.failAsync(done));
    });

    it('should limit the number of results, but display the total count', (done) => {

        exchangeService.historicTransactions(null, {limit: 4, page: 0})
            .then(transactions => {
                expect(transactions.count).toBe(10);
                expect(transactions.data.length).toBe(4);
                expect(_.pluck(transactions.data, 'id')).toEqual(jasmine.arrayContaining([
                        '10009',
                        '10008',
                        '10007',
                        '10006',
                ]));
            })
            .then(done)
            .catch(helpers.failAsync(done));
     });
});
