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
var r = require('rethinkdb');

var helpers = require('../../support/helpers');

var connector = require('../../../lib/sawtooth/model/db_connector');
var transaction = require('../../../lib/sawtooth/model/transaction');
var consts = require('../../../lib/sawtooth/constants');

describe('Transaction', () => {

    beforeEach((done) => {
        connector.exec(db => db.table('txn_list').insert([
                {
                    "Dependencies": [
                        "268ab792e3bba9a8" ,
                        "6a31fcb038352f6c" ,
                        "847a85055a35873b"
                    ] ,
                    "Identifier":  "8edfee5e9f4e9839" ,
                    "InBlock":  "227d35abfe236699" ,
                    "Nonce": 1463428938 ,
                    "Signature":  "some_very_long_signature_string" ,
                    "Status": 2 ,
                    "TransactionType":  "/MarketPlaceTransaction" ,
                    "Update": {
                        "FinalLiabilityID":  "268ab792e3bba9a8" ,
                        "InitialCount": 1 ,
                        "InitialLiabilityID":  "6a31fcb038352f6c" ,
                        "OfferIDList": [
                            "847a85055a35873b"
                        ] ,
                        "UpdateType":  "/mktplace.transactions.ExchangeUpdate/Exchange"
                    } ,
                    "id":  "8edfee5e9f4e9839"
                },
                {
                    "Dependencies":[
                        "0d731a6ec5c8f1f7",
                        "434c2b48b90e7547",
                        "e42d9104b6d8839c"
                    ],
                    "Identifier":"847a85055a35873b",
                    "InBlock":"be44dfb552338e5f",
                    "Nonce":1463428289,
                    "Signature":"another_very_long_signature",
                    "Status":1,
                    "TransactionType":"/MarketPlaceTransaction",
                    "Update": {
                        "CreatorID":"434c2b48b90e7547",
                        "Description":"",
                        "Execution":"ExecuteOncePerParticipant",
                        "InputID":"e42d9104b6d8839c",
                        "Maximum":1,
                        "Minimum":1,
                        "Name":"/offer/provision/USD",
                        "OutputID":"0d731a6ec5c8f1f7",
                        "Ratio":1000,
                        "UpdateType":"/mktplace.transactions.SellOfferUpdate/Register"
                    },
                    "id":"847a85055a35873b"
                }
            ]))
            .then(() => helpers.createBlock('8d36385306f25fcc', [
                        {
                            "account":  "947cbd0b3c927f0f" ,
                            "asset":  "9c8b57499d6f6aff" ,
                            "count": 1 ,
                            "creator":  "3ef683039b19f207" ,
                            "description":  "" ,
                            "id":  "6a31fcb038352f6c" ,
                            "name":  "/holding/token" ,
                            "object-type":  "Holding"
                        },
                        {
                            "account":  "947cbd0b3c927f0f" ,
                            "asset":  "b4d6da66dfe7d772" ,
                            "count": 1000 ,
                            "creator":  "3ef683039b19f207" ,
                            "description":  "Moneys!" ,
                            "id":  "268ab792e3bba9a8" ,
                            "name":  "/holding/USD" ,
                            "object-type":  "Holding"
                        },
                        {
                            "creator":  "434c2b48b90e7547" ,
                            "description":  "" ,
                            "execution":  "ExecuteOncePerParticipant" ,
                            "execution-state": {
                                "ParticipantList": [
                                    "3ef683039b19f207" ,
                                    "fde99309ef6be999"
                                ]
                            } ,
                            "id":  "847a85055a35873b" ,
                            "input":  "e42d9104b6d8839c" ,
                            "maximum": 1 ,
                            "minimum": 1 ,
                            "name":  "/offer/provision/USD" ,
                            "object-type":  "SellOffer" ,
                            "output":  "0d731a6ec5c8f1f7" ,
                            "ratio": 1000
                        },


            ]))
            .then(done)
            .catch(helpers.failAsync(done));
    });

    afterEach((done) => {
        connector.exec(db => db.table('txn_list').delete())
            .then(connector.thenExec(db => db.table('transactions').delete()))
            .then(helpers.thenCleanBlock('8d36385306f25fcc'))
            .then(done)
            .catch(helpers.failAsync(done));
    });

    describe('all', () => {

        it('should return all', (done) => {
            transaction.all({asArray: true})
                .then(transactions => {
                    expect(transactions.length).toBe(2);
                    expect(_.pluck(transactions, 'id')).toEqual([
                        '8edfee5e9f4e9839',
                        '847a85055a35873b',
                    ]);
                })
                .then(done)
                .catch(helpers.failAsync(done));
        });

        it('should respect paging', (done) => {
            transaction.all({asArray: true, page: 1, limit: 1})
                .then(transactions => {
                    expect(transactions.length).toBe(1);
                    expect(_.pluck(transactions, 'id')).toEqual([
                        '847a85055a35873b',
                    ]);
                })
                .then(done)
                .catch(helpers.failAsync(done));
        });
    });

    describe('count', () => {

        it('should count based all', (done) => {
            transaction.count({})
                .then(n => {
                    expect(n).toBe(2);
                })
                .then(done)
                .catch(helpers.failAsync(done));
        });

        it('should count based filter', (done) => {
            transaction.count({Status: consts.TransactionStatuses.COMMITTED})
                .then(n => {
                    expect(n).toBe(1);
                })
                .then(done)
                .catch(helpers.failAsync(done));
        });
    });

    describe('findExact', () => {

        it('should return results by exact query', (done) => {
            transaction.findExact(
                    r.and(r.row('Status').eq(consts.TransactionStatuses.COMMITTED),
                          r.row('Update')('UpdateType').eq('/mktplace.transactions.ExchangeUpdate/Exchange')),
                    {asArray: true})
                .then(transactions => {
                    expect(transactions.length).toBe(1);
                    expect(_.pluck(transactions, 'id')).toEqual(jasmine.arrayContaining([
                            '8edfee5e9f4e9839',
                    ]));
                })
                .then(done)
                .catch(helpers.failAsync(done));
        });

        it('should return empty results when none are found', (done) => {
            transaction.findExact(
                    r.and(r.row('Status').eq(consts.TransactionStatuses.PENDING),
                          r.row('Update')('UpdateType').eq('/mktplace.transactions.HoldingUpdate/Register')),
                    {asArray: true})
                .then(transactions => {
                    expect(transactions).toEqual([]);
                })
                .then(done)
                .catch(helpers.failAsync(done));

        });

        it('should respect limits on results', (done) => {
            transaction.findExact({}, {asArray: true, limit: 1})
                .then(transactions => {
                    expect(_.pluck(transactions, 'id')).toEqual([
                        '8edfee5e9f4e9839',
                    ]);
                })
                .then(done)
                .catch(helpers.failAsync(done));
        });
    });
});
