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

describe("ExchangeService", () => {

    beforeEach((done) => {
        connector.exec(db => 
                db.table('txn_list').insert([
                    {
                        // annotated transaction fields
                        id: '10dadf6340a1fb14',
                        ledgerId: '10dadf6340a1fb14',
                        blockid: '123456',
                        Status: consts.TransactionStatuses.PENDING,
                        creator: '61b4746fd90b7cb2',
                        created: Date.now(),

                        // Original transaction fields
                        TransactionType: '/MarketPlaceTransaction',
                        Signature: 'some_long_signature_string',
                        Nonce: 59568591313305.586,
                        Updates: [{
                            CreatorId: '61b4746fd90b7cb2',
                             "UpdateType" : "Exchange",
                             OfferIdList: ['63fab542a3415ce'],
                        }],
                        sellOffer: {
                            ratio: 1
                        }
                    },
                    {
                        // annotated transaction fields
                        id: '873ae7a00c767a57',
                        ledgerId: '873ae7a00c767a57',
                        blockid: '123456',
                        Status: consts.TransactionStatuses.COMMITTED,
                        creator: '61b4746fd90b7cb2',
                        created: Date.now(),

                        // Original transaction fields
                        TransactionType: '/MarketPlaceTransaction',
                        Signature: 'some_long_signature_string',
                        Nonce: 59568591313305.586,
                        Updates: [{
                            CreatorId: '61b4746fd90b7cb2',
                             "UpdateType" : "Exchange",
                             OfferIdList: ['63fab542a3415ce'],
                        }],
                        sellOffer: {
                            ratio: 1
                        }
                    },

                    {
                        // annotated transaction fields
                        id: '7f61dag340a1fb14',
                        ledgerId: '7f61dag340a1fb14',
                        blockid: '123456',
                        Status: consts.TransactionStatuses.PENDING,
                        creator: '61b4746fd90b7cb2',
                        created: Date.now(),

                        // Original transaction fields
                        TransactionType: '/MarketPlaceTransaction',
                        Signature: 'some_long_signature_string',
                        Nonce: 59568591313305.586,
                        Update: [{
                            CreatorId: '61b4746fd90b7cb2',
                            ObjectId: '01f4e11442867022',
                            UpdateType: 'UnregisterSellOffer',
                        }],
                        sellOffer: {
                            ratio: 1
                        }
                    },

                    {
                        id: '63fab542a3415ce',
                        ledgerId: '63fab542a3415ce',
                        blockid: '111222',
                        Status: consts.TransactionStatuses.PENDING,
                        creator: '3e9c534c01340ee7',
                        created: Date.now(),

                        TransactionType: '/MarketPlaceTransaction',
                        Signature: 'some_other_long_signature_string',
                        Nonce: 452743709641932.7,
                        Update: {
                            CreatorId: '3e9c534c01340ee7',
                            UpdateType: 'RegisterSellOffer'
                        },
                        sellOffer: {
                            ratio: 1
                        }
                    },
                    {
                        "id" : "597d9ca0aad8446d",
                        "Status" : consts.TransactionStatuses.FAILED,
                        "Nonce" : 1457974424.326741,
                        "blockid" : "24624d20478b630d",
                        "creator" : "2fc42f27eaac00e8",
                        "sellOffer" : {
                            "object-type" : "SellOffer",
                             "id" : "2d0d68428c4340fb",
                             "ratio" : 60,
                             "description" : "",
                             "offer_type" : "team_buyback",
                             "creator" : "637349cc929f5713",
                             "maximum" : 9223372036854775807,
                             "output" : "46174eb07635954b",
                             "fqname" : "//immxleague/offer/buyback/east4",
                             "minimum" : 0,
                             "input" : "e50375f50e944988",
                             "execution-state" : {
                                 "ParticipantList" : [ ]
                             },
                             "execution" : "Any",
                             "name" : "/offer/buyback/east4"
                         },
                         "created" : 1457974424734,
                         "Updates" : [{
                             "UpdateType" : "Exchange",
                             "FinalLiabilityId" : "40e76b0d69027978",
                             "InitialLiabilityId" : "ea3206b95cc91663",
                             "InitialCount" : 1,
                             "OfferIdList" : [
                                 "2d0d68428c4340fb"
                             ]
                         }],
                         "InBlock" : "failed",
                         "Dependencies" : [ ],
                         "ledgerId" : "597d9ca0aad8446d",
                         "Signature" : "G4LmBOauo+qwvBnCxSwSdgRwki6OZZ+TFB3xHOHUVK7H0aJPkhXCUYnNZhL7aP40MDdY3VzkjxHz1QFjVdPsFws=",
                         "TransactionType" : "/MarketPlaceTransaction"
                    },
                    {
                        "Dependencies": [
                            "976b0b4fba8ad430",
                            "deb3b939f5230e95"
                        ],
                        "InBlock":  "0884d1a1667da4f9",
                        "Nonce": 1466702571,
                        "Signature":  "IIj0ieIGJJdQ5YATEY6dhzkyPe3DZC1W1hSXNIKpWyLyRbTGDz5qKO5OhAMVssF8F7SKaZ+4R1ufpoCVO3xqgI0=",
                        "Status": consts.TransactionStatuses.COMMITTED,
                        "TransactionType":  "/MarketPlaceTransaction",
                        "Updates": [{
                            "FinalLiabilityId":  "976b0b4fba8ad430",
                            "InitialCount": 15,
                            "InitialLiabilityId":  "deb3b939f5230e95",
                            "OfferIdList": [ ],
                            "UpdateType":  "Exchange"
                        }],
                        "blockid":  "55cb01eb05ae3b38",
                        "created": 1466702572323,
                        "creator":  "61b4746fd90b7cb2",
                        "id":  "d477503af293cf22"
                    }
        ]))
                  .then(() => helpers.createBlock('123242', [
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
                        },
                        {
                            "account":  "48d0c574a422bdf9" ,
                            "asset":  "6e45fc365219904f" ,
                            "count": 10 ,
                            "creator":  "40fd34a6355ef87a" ,
                            "description":  "" ,
                            "id":  "ea3206b95cc91663" ,
                            "name":  "/holding/team/east4" ,
                            "object-type":  "Holding"
                        },
                        {
                            "account":  "48d0c574a422bdf9" ,
                            "asset":  "70afa6a11ed3bb45" ,
                            "count": 10000,
                            "creator":  "40fd34a6355ef87a" ,
                            "description":  "" ,
                            "id":  "40e76b0d69027978" ,
                            "name":  "/holding/mikels" ,
                            "object-type":  "Holding"
                        },
            ]))
            .then(done)
            .catch(e => {
                console.log("beforeEach", e);
                done.fail(e);
            });
    });

    afterEach((done) => {
    
        connector.exec(db => db.table('txn_list').delete())
            .then(connector.thenExec(db => db.table('transactions').delete()))
            .then(helpers.thenCleanBlock('123242'))
            .then(done)
            .catch(helpers.failAsync(done));
    });

    describe('historicTransactions', () => {
        it('should only return committed or failed ExchangeUpdates', (done) => {

            exchangeService.historicTransactions()
                .then(transactions => {
                    expect(transactions.count).toBe(2);
                    expect(_.pluck(transactions.data, 'id')).toEqual([
                            '873ae7a00c767a57',
                            '597d9ca0aad8446d',
                    ]);
                    expect(_.pluck(transactions.data, 'failed')).toEqual([false, true]);
                })
                .then(done)
                .catch(helpers.failAsync(done));
        });

        it('should respect filter: assetId', (done) => {
            exchangeService.historicTransactions(null, {filter: {assetId: '6e45fc365219904f'}})
                .then(transactions => {
                    expect(transactions.count).toBe(1);
                    expect(_.pluck(transactions.data, 'id')).toEqual([
                            '597d9ca0aad8446d',
                    ]);
                })
                .then(done)
                .catch(helpers.failAsync(done));
        });

        it('should respect filter: holdingId', (done) => {
            exchangeService.historicTransactions(null, {filter: {holdingId: '40e76b0d69027978'}})
                .then(transactions => {
                    expect(transactions.count).toBe(1);
                    expect(_.pluck(transactions.data, 'id')).toEqual([
                            '597d9ca0aad8446d',
                    ]);
                })
                .then(done)
                .catch(helpers.failAsync(done));
        });

        it('should return transfers when creator is specified', (done) =>  {
            exchangeService.historicTransactions('61b4746fd90b7cb2')
                .then(transactions => {
                    expect(transactions.count).toBe(2);
                    expect(_.pluck(transactions.data, 'id')).toEqual([
                            '873ae7a00c767a57',
                            'd477503af293cf22',
                    ]);
                })
                .then(done)
                .catch(helpers.failAsync(done));
        });

    });

});
