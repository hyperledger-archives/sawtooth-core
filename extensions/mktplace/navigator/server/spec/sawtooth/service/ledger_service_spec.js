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

let ledgerService = require('../../../lib/sawtooth/service/ledger_service');
let transaction = require('../../../lib/sawtooth/model/transaction');
let helpers = require('../../support/helpers');
var connector = require('../../../lib/sawtooth/model/db_connector');

describe('LedgerService', () => {

    beforeEach((done) => 
        helpers.createBlock('1234ls_test', [])
            .then(done)
            .catch(helpers.failAsync(done)));

    afterEach((done) =>
        connector.exec(db => db.table('transactions').delete())
            .then(helpers.thenCleanBlock('1234ls_test'))
            .then(done)
            .catch(helpers.failAsync(done)));

    describe('storeTransaction', () => {

        it('should add all the default annotations', (done) => {

            ledgerService.storeTransaction('1122334455667788', {
                    // Original transaction fields
                    TransactionType: '/MarketPlaceTransaction',
                    Signature: 'some_long_signature_string',
                    Nonce: 59568591313305.586,
                    Updates: [{
                        CreatorId: '61b4746fd90b7cb2',
                        FinalLiabilityId: "9b598458273cf19d",
                        InitialCount: 1,
                        InitialLiabilityId: "dd994a04101aa8dc",
                        OfferIdList: ["0448ee05c78306db"],
                        UpdateType: "Exchange",
                    }],
            })
            .then((id) => {
                expect(id).toBe('1122334455667788');
            })
            .then(() => transaction.get('1122334455667788'))
            .then(savedTransaction => {
                expect(savedTransaction.id).toBe('1122334455667788');
                expect(savedTransaction.blockid).toBe('1234ls_test');
            })
            .then(done)
            .catch(helpers.failAsync(done));
        });
    });
});
