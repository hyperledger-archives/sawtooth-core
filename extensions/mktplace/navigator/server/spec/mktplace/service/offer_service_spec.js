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
var offerService = require('../../../lib/mktplace/service/offer_service');
var consts = require('../../../lib/sawtooth/constants');
var {data} = require('./offer_service_data');

describe("OfferService", () => {

    beforeAll((done) => {
       helpers.createBlock('12345678',  data)
            .then(done)
            .catch(helpers.failAsync(done));
    });

    afterAll((done) => {
        helpers.cleanBlock('12345678')
            .then(done)
            .catch(helpers.failAsync(done));
    });

    describe('offer', () => {
        it('should get an offer by id', (done) =>
            offerService.offer('61b4746fd90b7cb2', '01f4e11442867022')
                .then(offer => {
                    expect(offer.id).toBe('01f4e11442867022');
                })
                .then(done)
                .catch(helpers.failAsync(done)));

    });

    describe('availableOffers', ()=> {

        it('should get all open offers available to the given user', (done) => {

            offerService.availableOffers('61b4746fd90b7cb2')
                .then(offers => {
                    expect(offers.count).toBe(3);
                    expect(offers.data.length).toBe(3);
                    expect(_.pluck(offers.data, 'id')).toEqual([
                        '01f4e11442867022',
                        '0448ee05c78306db',
                        '0b89652e39a8e1e1',
                    ]);
                })
                .then(done)
                .catch(helpers.failAsync(done));
        });

        it('should take a limit option', (done) => {
            offerService.availableOffers('61b4746fd90b7cb2', {limit: 1})
                .then(offers => {
                    expect(offers.count).toBe(3);
                    expect(offers.data.length).toBe(1);
                    expect(_.pluck(offers.data, 'id')).toEqual([
                        '01f4e11442867022',
                    ]);
                })
                .then(done)
                .catch(helpers.failAsync(done));
        });

        it('should take a limit and page option', (done) => {
            offerService.availableOffers('61b4746fd90b7cb2', {limit: 1, page: 0})
                .then(offers => {
                    expect(offers.count).toBe(3);
                    expect(offers.data.length).toBe(1);
                    expect(_.pluck(offers.data, 'id')).toEqual([
                        '01f4e11442867022',
                    ]);
                    expect(offers.hasMore).toBeTruthy();
                    expect(offers.nextPage).toBe(1);
                })
                .then(done)
                .catch(helpers.failAsync(done));
        });

        it('should take a filter option: participantId', (done) => {
            offerService.availableOffers('61b4746fd90b7cb2', {filter: {participantId: '4f2ede53e0e08e6f'}})
                .then(offers => {
                    expect(offers.count).toBe(2);
                    expect(offers.data.length).toBe(2);
                    expect(_.pluck(offers.data, 'id')).toEqual([
                        '01f4e11442867022',
                        '0448ee05c78306db',
                    ]);
                })
                .then(done)
                .catch(helpers.failAsync(done));
        });

        it('should tack a filter option: !participantId', (done) =>
            offerService.availableOffers('61b4746fd90b7cb2', {filter: {participantId: '!4f2ede53e0e08e6f'}})
                .then(offers => {
                    expect(offers.count).toBe(1);
                    expect(offers.data.length).toBe(1);
                    expect(_.pluck(offers.data, 'id')).toEqual([
                        '0b89652e39a8e1e1'
                    ]);
                })
                .then(done)
                .catch(helpers.failAsync(done)));

        it('should take a filter option: assetId', (done) => {

            offerService.availableOffers('61b4746fd90b7cb2', {filter: {assetId: 'c6cb5a1eb07af614'}})
                .then(offers => {
                    expect(offers.count).toBe(1);
                    expect(offers.data.length).toBe(1);
                    expect(_.pluck(offers.data, 'id')).toEqual([
                            '01f4e11442867022'
                    ]);
                })
                .then(done)
                .catch(helpers.failAsync(done));
        });

        it('should take a filter option: holdingId', (done) => {

            offerService.availableOffers('61b4746fd90b7cb2', {filter: {holdingId: 'dd994a04101aa8dc'}})
                .then(offers => {
                    expect(offers.count).toBe(1);
                    expect(offers.data.length).toBe(1);
                    expect(_.pluck(offers.data, 'id')).toEqual([
                            '0448ee05c78306db'
                    ]);
                })
                .then(done)
                .catch(helpers.failAsync(done));
        });

        it('should take a filter option: inputAssetId', (done) =>
            offerService.availableOffers('61b4746fd90b7cb2', {
                filters: {
                    inputAssetId: 'c6cb5a1eb07af614'
                }
            })
            .then(offers => {
                expect(offers.count).toBe(3);
                expect(offers.data.length).toBe(3);
                expect(_.pluck(offers.data , 'id')).toEqual([
                        '01f4e11442867022',
                        '0448ee05c78306db',
                        '0b89652e39a8e1e1'
                ]);
            })
            .then(done)
            .catch(helpers.failAsync(done)));
    });

    describe('offers', () => {

        it('should get open offers by creator', (done) => {
            offerService.offers('4f2ede53e0e08e6f')
                .then(offers => {
                    expect(offers.count).toBe(3);
                    expect(offers.data.length).toBe(3);
                    expect(_.pluck(offers.data, 'id')).toEqual([
                        '0c9fd266e7973144',
                        '01f4e11442867022',
                        '0448ee05c78306db',
                    ]);
                })
                .then(done)
                .catch(helpers.failAsync(done));
        });

        it('should get take a limit options', (done) => {
            offerService.offers('4f2ede53e0e08e6f', {limit: 1})
                .then(offers => {
                    expect(offers.count).toBe(3);
                    expect(offers.data.length).toBe(1);
                    expect(_.pluck(offers.data, 'id')).toEqual([
                        '0c9fd266e7973144',
                    ]);
                })
                .then(done)
                .catch(helpers.failAsync(done));
        });

        it('should return an empty array when none are found', (done) => {
            offerService.offers('some_unknownid')
                .then(offers => {
                    expect(offers.count).toBe(0);
                    expect(offers.data).toEqual([]);
                })
                .then(done)
                .catch(helpers.failAsync(done));
        });
    });

    describe('with pending offers', () => {
        beforeEach((done) => {
            connector.exec((db) => db.table('transactions').insert([
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
                        Updates: [{
                            "CreatorId" : "3e9c534c01340ee7",
                            "Description" : "",
                            "Execution" : "Any",
                            "InputId" : "79386c0a237df4e7",
                            "Maximum" : 1000000000,
                            "Minimum" : 1,
                            "Name" : "",
                            "OutputId" : "9b598458273cf19d",
                            "Ratio" : 21,
                            "UpdateType" : "RegisterSellOffer"
                        }],
                    }
            ]))
            .then(done)
            .catch(helpers.failAsync(done));
        });

        afterEach((done) => {
            connector.exec((db) => db.table('transactions').delete())
                .then(done)
                .catch(helpers.failAsync(done));
        });

        it('offers should return this as an offer', (done) => {
            offerService.offers('3e9c534c01340ee7')
                .then(offers => {
                    expect(offers.count).toBe(1);
                    expect(offers.data.length).toBe(1);
                    expect(offers.data[0].id).toBe('63fab542a3415ce');
                    expect(offers.data[0].pending).toBeTruthy();
                })
                .then(done)
                .catch(helpers.failAsync(done));
        });

        it('availableOffers should return this as an offer', (done) => {
            offerService.availableOffers('3e9c534c01340ee7')
                .then(offers => {
                    expect(offers.count).toBe(5);
                    expect(offers.data.length).toBe(5);
                    expect(_.pluck(offers.data, 'id')).toEqual([
                        '63fab542a3415ce',
                        '0c9fd266e7973144',
                        '01f4e11442867022',
                        '0448ee05c78306db',
                        '0b89652e39a8e1e1',
                    ]);
                    expect(_.pluck(offers.data, 'pending')).toEqual([
                        true,
                        undefined,
                        undefined,
                        undefined,
                        undefined,
                    ]);
                })
                .then(done)
                .catch(helpers.failAsync(done));
        });

        it('should still obey limits', (done) => {
            offerService.availableOffers('3e9c534c01340ee7', {limit: 3, page: 0})
                .then(offers => {
                    expect(offers.count).toBe(5);
                    expect(offers.data.length).toBe(3);
                    expect(_.pluck(offers.data, 'id')).toEqual([
                        '63fab542a3415ce',
                        '0c9fd266e7973144',
                        '01f4e11442867022',
                    ]);
                    expect(_.pluck(offers.data, 'pending')).toEqual([
                        true,
                        undefined,
                        undefined,
                    ]);
                })
                .then(done)
                .catch(helpers.failAsync(done));
        });

    });

    describe('removed offers', () => {
        beforeEach((done) => {
            connector.exec((db) => db.table('transactions').insert([
                    {
                        // annotated transaction fields
                        id: '7f61dag340a1fb14',
                        ledgerId: '7f61dag340a1fb14',
                        blockid: '123456',
                        Status: consts.TransactionStatuses.PENDING,
                        creator: '4f2ede53e0e08e6f',
                        created: Date.now(),

                        // Original transaction fields
                        TransactionType: '/MarketPlaceTransaction',
                        Signature: 'some_long_signature_string',
                        Nonce: 59568591313305.586,
                        Updates: [{
                            CreatorId: '4f2ede53e0e08e6f',
                            ObjectId: '01f4e11442867022',
                            UpdateType: 'UnregisterSellOffer',
                        }],
                    },
            ]))
            .then(done)
            .catch(helpers.failAsync(done));
        });

        afterEach((done) => {
            connector.exec((db) => db.table('transactions').delete())
                .then(done)
                .catch(helpers.failAsync(done));
        });

        it('offers should return this as an offer', (done) => {
            offerService.offers('4f2ede53e0e08e6f')
                .then(offers => {
                    expect(offers.count).toBe(3);
                    expect(offers.data.length).toBe(3);
                    expect(_.pluck(offers.data, 'id')).toEqual([
                        '0c9fd266e7973144',
                        '01f4e11442867022',
                        '0448ee05c78306db',
                    ]);
                    expect(_.pluck(offers.data, 'revoked')).toEqual([
                        false,
                        true,
                        false,
                    ]);
                })
                .then(done)
                .catch(helpers.failAsync(done));
        });

        it('availableOffers should return this as an offer', (done) => {
            offerService.availableOffers('4f2ede53e0e08e6f')
                .then(offers => {
                    expect(offers.count).toBe(4);
                    expect(offers.data.length).toBe(4);
                    expect(_.pluck(offers.data, 'id')).toEqual([
                            '0c9fd266e7973144',
                            '01f4e11442867022',
                            '0448ee05c78306db',
                            '0b89652e39a8e1e1',
                    ]);
                    expect(_.pluck(offers.data, 'revoked')).toEqual([
                        false,
                        true,
                        false,
                        false,
                    ]);
                })
                .then(done)
                .catch(helpers.failAsync(done));
        });

        it('should still obey limits', (done) => {
            offerService.availableOffers('4f2ede53e0e08e6f', {limit: 3})
                .then(offers => {
                    expect(offers.count).toBe(4);
                    expect(offers.data.length).toBe(3);
                    expect(_.pluck(offers.data, 'id')).toEqual([
                        '0c9fd266e7973144',
                        '01f4e11442867022',
                        '0448ee05c78306db',
                    ]);
                    expect(_.pluck(offers.data, 'revoked')).toEqual([
                        false,
                        true,
                        false,
                    ]);
                })
                .then(done)
                .catch(helpers.failAsync(done));
        });

    });

    describe('exchanges in process', () => {
    
        beforeEach((done) => {
            connector.exec((db) => db.table('transactions').insert([
                    {
                        "id" : "4bf2a65310409a52",
                        "Status" : 1,
                        "created" : 1457558804993,
                        "ledgerId" : "4bf2a65310409a52",
                        "creator" : "4f2ede53e0e08e6f",
                        "blockid" : "12345678",
                        "Dependencies" : [ ],
                        "Nonce" : 1457558804.852492,
                        "Signature" : "some_other_long_signature_string",
                        "TransactionType" : "/MarketPlaceTransaction",
                        "Updates" : [{
                            "FinalLiabilityId" : "9b598458273cf19d",
                            "InitialCount" : 1,
                            "InitialLiabilityId" : "991ba2e592243d51",
                            "OfferIdList" : [
                                "01f4e11442867022"
                            ],
                            "UpdateType" : "Exchange"
                         }],
                         "sellOffer" : {
                             "id" : "01f4e11442867022",
                             "creator" : "4f2ede53e0e08e6f",
                             // We don't really care about hte rest of the fields
                             // so we'll leav them out
                         }
                    }
            ]))
            .then(done)
            .catch(helpers.failAsync(done));
        });

        it('availableOffers should return this as an offer', (done) => {
            offerService.availableOffers('4f2ede53e0e08e6f')
                .then(offers => {
                    expect(offers.count).toBe(4);
                    expect(offers.data.length).toBe(4);
                    expect(_.pluck(offers.data, 'id')).toEqual([
                        '0c9fd266e7973144',
                        '01f4e11442867022',
                        '0448ee05c78306db',
                        '0b89652e39a8e1e1',
                    ]);
                    expect(_.pluck(offers.data, 'processing')).toEqual([
                        false,
                        true,
                        false,
                        false,
                    ]);
                })
                .then(done)
                .catch(helpers.failAsync(done));
        });

        afterEach((done) => {
            connector.exec((db) => db.table('transactions').delete())
                .then(done)
                .catch(helpers.failAsync(done));
        });

    });

});
