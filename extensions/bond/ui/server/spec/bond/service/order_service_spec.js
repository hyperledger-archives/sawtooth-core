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
var orderService = require('../../../lib/bond/service/order_service');

describe('ParticipantService', () => {

    beforeEach(done => {
        helpers.createBlock('112233', [
            {
                "action":  "Buy",
                "creator-id":  "3932250c4877136ee99bf76e5ffbb50b7fbd46d6788340d294225f67b3a2e98c",
                "firm-id":  "fec9a7ed78845f26678c8433f62029d84f33ce0fa58bfbbf05b64b34f4187498",
                "id":  "916dfd62f6b6bfed7017556f94f03a78600c1c0e51e0cad32d2156746930f6ac",
                "isin":  "US22160KAF21",
                "limit-price":  "98-05.875",
                "limit-yield": 0.015,
                "object-id":  "916dfd62f6b6bfed7017556f94f03a78600c1c0e51e0cad32d2156746930f6ac",
                "object-type":  "order",
                "order-type":  "Limit",
                "quantity": 100000,
                "ref-count": 0,
                "status":  "Open"
            },
            {
                "action":  "Sell",
                "creator-id":  "3932250c4877136ee99bf76e5ffbb50b7fbd46d6788340d294225f67b3a2e98c",
                "firm-id":  "fec9a7ed78845f26678c8433f62029d84f33ce0fa58bfbbf05b64b34f4187498",
                "id":  "c7c970769ec2726cee2554f9f7baba449d01d3590abcf782bdbee03095c95bf7",
                "cusip":  "035242AP1",
                "object-id":  "c7c970769ec2726cee2554f9f7baba449d01d3590abcf782bdbee03095c95bf7",
                "object-type":  "order",
                "order-type":  "Market",
                "quantity": 100000,
                "quote-id":  "be1c91377425cc14c18510a0b4fd516ba4edf6360afdd02e2c171e6ca77584ab",
                "ref-count": 1,
                "status":  "Settled"
            },
            {
                "amount-outstanding":  "11000000000",
                "corporate-debt-ratings": {
                    "Moodys":  "A3",
                    "S&P":  "A-"
                },
                "coupon-rate":  "3.65",
                "coupon-type":  "fixed",
                "cusip":  "035242AP1",
                "face-value": 1000,
                "first-settlement-date":  "01/25/2016",
                "id":  "bfc8ba09734e4fb46d603b0fa058e6ea4b25778a4910afb1b3c9eb660fa280ee",
                "isin":  "US035242AP13",
                "issuer":  "ABIBB",
                "maturity-date":  "02/01/2026",
                "object-id":  "bfc8ba09734e4fb46d603b0fa058e6ea4b25778a4910afb1b3c9eb660fa280ee",
                "object-type":  "bond",
                "ref-count": 0
            },
            {
                "amount-outstanding":  "1200000000",
                "corporate-debt-ratings": {
                    "Moodys":  "A1",
                    "S&P":  "A+"
                },
                "coupon-rate":  "1.7",
                "coupon-type":  "fixed",
                "cusip":  "22160KAF2",
                "face-value": 1000,
                "first-settlement-date":  "12/07/2012",
                "id":  "60441b8c44b67a71f815b903cad16a1e934a7fefed609f69fe67005755f1a4b9",
                "isin":  "US22160KAF21",
                "issuer":  "COST",
                "maturity-date":  "12/15/2019",
                "object-id":  "60441b8c44b67a71f815b903cad16a1e934a7fefed609f69fe67005755f1a4b9",
                "object-type":  "bond",
                "ref-count": 4
            },
            {
                "creator-id":  "3932250c4877136ee99bf76e5ffbb50b7fbd46d6788340d294225f67b3a2e98c",
                "id":  "3932250c4877136ee99bf76e5ffbb50b7fbd46d6788340d294225f67b3a2e98c",
                "key-id":  "16RjpB4ZWHmHqMGxseuyT5vDnDVgMurPiT",
                "object-id":  "3932250c4877136ee99bf76e5ffbb50b7fbd46d6788340d294225f67b3a2e98c",
                "object-type":  "participant",
                "username":  "FirstParticipant"
            }
        ])
        .then(done)
        .catch(helpers.failAsync(done));
    });

    afterEach(done => {
        helpers.cleanBlock('112233')
            .then(connector.thenExec(db => db.table('transactions').delete()))
            .then(done)
            .catch(helpers.failAsync(done));
    });

    describe('orders()', () => {
        it('should merge the bonds by isin or cusip', (done) => 
            orderService.orders('3932250c4877136ee99bf76e5ffbb50b7fbd46d6788340d294225f67b3a2e98c')
                .then(orders => {
                    expect(orders.count).toBe(2);
                    expect(orders.data).toEqual([
                    {
                        "action":  "Buy",
                        "creator-id":  "3932250c4877136ee99bf76e5ffbb50b7fbd46d6788340d294225f67b3a2e98c",
                        "firm-id":  "fec9a7ed78845f26678c8433f62029d84f33ce0fa58bfbbf05b64b34f4187498",
                        "id":  "916dfd62f6b6bfed7017556f94f03a78600c1c0e51e0cad32d2156746930f6ac",
                        "isin":  "US22160KAF21",
                        "limit-price":  "98-05.875",
                        "limit-yield": 0.015,
                        "object-id":  "916dfd62f6b6bfed7017556f94f03a78600c1c0e51e0cad32d2156746930f6ac",
                        "object-type":  "order",
                        "order-type":  "Limit",
                        "quantity": 100000,
                        "ref-count": 0,
                        "status":  "Open",
                        "bond": {
                            "amount-outstanding":  "1200000000",
                            "corporate-debt-ratings": {
                                "Moodys":  "A1",
                                "S&P":  "A+"
                            },
                            "coupon-rate":  "1.7",
                            "coupon-type":  "fixed",
                            "cusip":  "22160KAF2",
                            "face-value": 1000,
                            "first-settlement-date":  "12/07/2012",
                            "id":  "60441b8c44b67a71f815b903cad16a1e934a7fefed609f69fe67005755f1a4b9",
                            "isin":  "US22160KAF21",
                            "issuer":  "COST",
                            "maturity-date":  "12/15/2019",
                            "object-id":  "60441b8c44b67a71f815b903cad16a1e934a7fefed609f69fe67005755f1a4b9",
                            "object-type":  "bond",
                            "ref-count": 4
                        },
                        "trader": "FirstParticipant",
                    },
                    {
                        "action":  "Sell",
                        "creator-id":  "3932250c4877136ee99bf76e5ffbb50b7fbd46d6788340d294225f67b3a2e98c",
                        "firm-id":  "fec9a7ed78845f26678c8433f62029d84f33ce0fa58bfbbf05b64b34f4187498",
                        "id":  "c7c970769ec2726cee2554f9f7baba449d01d3590abcf782bdbee03095c95bf7",
                        "cusip":  "035242AP1",
                        "object-id":  "c7c970769ec2726cee2554f9f7baba449d01d3590abcf782bdbee03095c95bf7",
                        "object-type":  "order",
                        "order-type":  "Market",
                        "quantity": 100000,
                        "quote-id":  "be1c91377425cc14c18510a0b4fd516ba4edf6360afdd02e2c171e6ca77584ab",
                        "ref-count": 1,
                        "status":  "Settled",
                        "bond": {
                            "amount-outstanding":  "11000000000",
                            "corporate-debt-ratings": {
                                "Moodys":  "A3",
                                "S&P":  "A-"
                            },
                            "coupon-rate":  "3.65",
                            "coupon-type":  "fixed",
                            "cusip":  "035242AP1",
                            "face-value": 1000,
                            "first-settlement-date":  "01/25/2016",
                            "id":  "bfc8ba09734e4fb46d603b0fa058e6ea4b25778a4910afb1b3c9eb660fa280ee",
                            "isin":  "US035242AP13",
                            "issuer":  "ABIBB",
                            "maturity-date":  "02/01/2026",
                            "object-id":  "bfc8ba09734e4fb46d603b0fa058e6ea4b25778a4910afb1b3c9eb660fa280ee",
                            "object-type":  "bond",
                            "ref-count": 0
                        },
                        "trader": "FirstParticipant",
                    },
                    ]);
                })
                .then(done)
                .catch(helpers.failAsync(done)));

        it('should respect paging and limits', (done) =>
            orderService.orders('3932250c4877136ee99bf76e5ffbb50b7fbd46d6788340d294225f67b3a2e98c',
                                {page: 0, limit: 1})
                .then(orders => {
                    expect(orders.count).toBe(2);
                    expect(orders.data.length).toBe(1);
                    expect(_.pluck(orders.data, 'id')).toEqual([
                            '916dfd62f6b6bfed7017556f94f03a78600c1c0e51e0cad32d2156746930f6ac',
                    ]);
                    expect(orders.nextPage).toBe(1);
                    expect(orders.hasMore).toBeTruthy();
                })
                .then(done)
                .catch(helpers.failAsync(done)));

        describe('with pending transactions', () => {
            beforeEach((done) =>
                connector.exec(db => db.table('transactions').insert([
                    {
                        "Dependencies": [ ],
                        "InBlock":  "PENDING" ,
                        "Nonce": 1470681601 ,
                        "Signature":  "H4OYO77YsVUoHw+MoUa2MxCUmxWunrJ08tjd4wgz7GoOAO8HNenMmP63qh49Fv/1fPFa9GKhIGz0kltr0M802G8=" ,
                        "Status": 1 ,
                        "TransactionType":  "/BondTransaction" ,
                        "Updates": [
                        {
                            "Action":  "Buy" ,
                            "FirmId":  "scgvaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" ,
                            "Isin":  "US22160KAF21" ,
                            "LimitPrice":  "103" ,
                            "Nonce":  "cmRxI\tQxDoYlpUn" ,
                            "ObjectId":  "ecf174aa534b240b43241bc3c85c3b62b3fbc4f9cf76ab627bc477b26639b15d" ,
                            "OrderType":  "Limit" ,
                            "Quantity": 100000 ,
                            "UpdateType":  "CreateOrder"
                        }
                        ] ,
                        "blockid":  "3570db24ee6dc026" ,
                        "created": 1470681602549 ,
                        "creator": null ,
                        'creator-id': '3932250c4877136ee99bf76e5ffbb50b7fbd46d6788340d294225f67b3a2e98c',
                        "id":  "2c8d181b80055c82" ,
                        "key-id":  "1HsdmRA8CXCeKVgibkTX9zC8xTmvV4sJ5V"
                    }
                ]))
                .then(done)
                .catch(helpers.failAsync(done)));


            it('should return pending transactions for creator', (done) =>
                orderService.orders('3932250c4877136ee99bf76e5ffbb50b7fbd46d6788340d294225f67b3a2e98c')
                    .then(orders => {
                        expect(orders.count).toBe(3);
                        expect(orders.data.length).toBe(3);
                        expect(_.pluck(orders.data, 'id')).toEqual([
                            'ecf174aa534b240b43241bc3c85c3b62b3fbc4f9cf76ab627bc477b26639b15d',
                            '916dfd62f6b6bfed7017556f94f03a78600c1c0e51e0cad32d2156746930f6ac',
                            'c7c970769ec2726cee2554f9f7baba449d01d3590abcf782bdbee03095c95bf7',
                        ]);
                    })
                    .then(done)
                    .catch(helpers.failAsync(done)));

        });
    });

});
