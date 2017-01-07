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
var quoteService = require('../../../lib/bond/service/quote_service');

describe('QuoteService', () => {
    beforeEach((done) =>
        helpers.createBlock('112233', [
            {
                "ask-price":  "98-06 7/8" ,
                "ask-qty": 0 ,
                "bid-price":  "98-05 7/8" ,
                "bid-qty": 1000000 ,
                "creator-id":  "3932250c4877136ee99bf76e5ffbb50b7fbd46d6788340d294225f67b3a2e98c" ,
                "firm":  "SCGV" ,
                "id":  "090c9eb0538da7a2f83b88ed72d275f3f1f27923da298df275ee83907a0222f1" ,
                "isin":  "US22160KAF21" ,
                "object-id":  "090c9eb0538da7a2f83b88ed72d275f3f1f27923da298df275ee83907a0222f1" ,
                "object-type":  "quote" ,
                "ref-count": 2 ,
                "status":  "Closed" ,
                "timestamp": 1470764511.605975
            },
            {
                "ask-price":  "97-06 7/8" ,
                "ask-qty": 900000 ,
                "bid-price":  "99-05 7/8" ,
                "bid-qty": 1000000 ,
                "creator-id":  "3932250c4877136ee99bf76e5ffbb50b7fbd46d6788340d294225f67b3a2e98c" ,
                "firm":  "SCGV" ,
                "id":  "c8d1ffcacae11e3fd6d2f2427783d9cc0c6c5d415eb5dc44a90537472687f49a" ,
                "isin":  "US22160KAF21" ,
                "object-id":  "c8d1ffcacae11e3fd6d2f2427783d9cc0c6c5d415eb5dc44a90537472687f49a" ,
                "object-type":  "quote" ,
                "ref-count": 1 ,
                "status":  "Open" ,
                "timestamp": 1470764511.605975
            },
            {
                "amount-outstanding":  "1200000000" ,
                "corporate-debt-ratings": {
                    "Moodys":  "A1" ,
                    "S&P":  "A+"
                } ,
                "coupon-frequency":  "Quarterly" ,
                "coupon-rate":  "1.7" ,
                "coupon-type":  "Fixed" ,
                "creator-id":  "3932250c4877136ee99bf76e5ffbb50b7fbd46d6788340d294225f67b3a2e98c" ,
                "cusip":  "22160KAF2" ,
                "face-value": 1000 ,
                "first-coupon-date":  "01/01/2013" ,
                "first-settlement-date":  "12/07/2012" ,
                "id":  "7d9e47fc91535063573880f6ae83e59251257e654aad8041d7ed8ac5f28c47e4" ,
                "isin":  "US22160KAF21" ,
                "issuer":  "COST" ,
                "maturity-date":  "12/15/2019" ,
                "object-id":  "7d9e47fc91535063573880f6ae83e59251257e654aad8041d7ed8ac5f28c47e4" ,
                "object-type":  "bond" ,
                "ref-count": 7
            }
        ])
        .then(done)
        .catch(helpers.failAsync(done)));

    afterEach(done =>
        helpers.cleanBlock('112233')
            .then(connector.thenExec(db => db.table('transactions').delete()))
            .then(done)
            .catch(helpers.failAsync(done)));

    describe('bondAndQuotes', () => {
        let participantId = '3932250c4877136ee99bf76e5ffbb50b7fbd46d6788340d294225f67b3a2e98c';

        it('should fetch the bond and its open quotes', (done) =>
            quoteService.bondAndQuotes(participantId, 'US22160KAF21')
                .then(({bond, quotes}) => {
                    expect(bond.id)
                        .toBe('7d9e47fc91535063573880f6ae83e59251257e654aad8041d7ed8ac5f28c47e4');
                    expect(quotes.count).toBe(1);
                    expect(quotes.data.length).toBe(1);
                    expect(quotes.data[0]['ask-price'])
                        .toBe('97-06 7/8');
                    expect(quotes.data[0].status)
                        .toBe('Open');
                })
                .then(done)
                .catch(helpers.failAsync(done)));

        describe('with pending quotes', () => {

            beforeEach((done) =>
                connector.exec(db => db.table('transactions').insert([
                    {
                        "Dependencies": [ ],
                        "InBlock":  "PENDING" ,
                        "Nonce": 1470773363 ,
                        "Signature":  "IMd6dWEueSHvjTFu/8EOgeqUpbpIdkGpzGV1WdaCn9kKGOwwmCe/SS70hznlCT768XqecANPP76stFusYuc1IRY=" ,
                        "Status": 1 ,
                        "TransactionType":  "/BondTransaction" ,
                        "Updates": [
                            {
                                "AskPrice":  "102 1/8" ,
                                "AskQty": 1000000 ,
                                "BidPrice":  "102" ,
                                "BidQty": 1000000 ,
                                "Firm":  "SCGV" ,
                                "Isin":  "US22160KAF21" ,
                                "ObjectId":  "32154533abc18051c5ec613bf48a1141f8672a9d5caaebb69cfb59718627ecac" ,
                                "UpdateType":  "CreateQuote"
                            }
                        ] ,
                        "blockid":  "b3744d200f403324" ,
                        "created": 1470773364106 ,
                        'creator-id': participantId,
                        "creator": null ,
                        "id":  "b462d6e7617828b9" ,
                        "key-id":  "1HsdmRA8CXCeKVgibkTX9zC8xTmvV4sJ5V"
                    }
                ]))
                .then(done)
                .catch(helpers.failAsync(done)));

            it('should fetch pending quotes for the user', (done) =>
                quoteService.bondAndQuotes(participantId, 'US22160KAF21')
                    .then(({bond, quotes}) => {
                        expect(bond.id)
                            .toBe('7d9e47fc91535063573880f6ae83e59251257e654aad8041d7ed8ac5f28c47e4');
                        expect(quotes.count).toBe(2);
                        expect(quotes.data.length).toBe(2);
                        expect(_.pluck(quotes.data, 'ask-price')).toEqual([
                                '97-06 7/8',
                                '102 1/8',
                        ]);
                        expect(_.pluck(quotes.data, 'bid-price')).toEqual([
                                "99-05 7/8",
                                '102',
                        ]);
                        expect(_.pluck(quotes.data, 'status')).toEqual([
                                'Open',
                                'Pending Commit',
                        ]);
                    })
                .then(done)
                .catch(helpers.failAsync(done)));

        });
    });


});
