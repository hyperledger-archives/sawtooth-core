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
var bondService = require('../../../lib/bond/service/bond_service');

describe('BondService', () => {

    beforeEach(done => {
        helpers.createBlock('112233', [
            {
                "amount-outstanding":  "11000000000" ,
                "corporate-debt-ratings": {
                    "Moodys":  "A3" ,
                    "S&P":  "A-"
                } ,
                "coupon-rate":  "3.65" ,
                "coupon-type":  "fixed" ,
                "cusip":  "035242AP1" ,
                "face-value": 1000 ,
                "first-settlement-date":  "01/25/2016" ,
                "id":  "bfc8ba09734e4fb46d603b0fa058e6ea4b25778a4910afb1b3c9eb660fa280ee" ,
                "isin":  "US035242AP13" ,
                "issuer":  "ABIBB" ,
                "maturity-date":  "02/01/2026" ,
                "object-id":  "bfc8ba09734e4fb46d603b0fa058e6ea4b25778a4910afb1b3c9eb660fa280ee" ,
                "object-type":  "bond" ,
                "ref-count": 0
            },
            {
                "amount-outstanding":  "1200000000" ,
                "corporate-debt-ratings": {
                    "Moodys":  "A1" ,
                    "S&P":  "A+"
                } ,
                "coupon-rate":  "1.7" ,
                "coupon-type":  "fixed" ,
                "cusip":  "22160KAF2" ,
                "face-value": 1000 ,
                "first-settlement-date":  "12/07/2012" ,
                "id":  "60441b8c44b67a71f815b903cad16a1e934a7fefed609f69fe67005755f1a4b9" ,
                "isin":  "US22160KAF21" ,
                "issuer":  "COST" ,
                "maturity-date":  "12/15/2019" ,
                "object-id":  "60441b8c44b67a71f815b903cad16a1e934a7fefed609f69fe67005755f1a4b9" ,
                "object-type":  "bond" ,
                "ref-count": 4
            },
            {
                "amount-outstanding":  "1500000000" ,
                "corporate-debt-ratings": {
                    "Fitch":  "BB" ,
                    "Moodys":  "B3" ,
                    "S&P":  "B+"
                } ,
                "coupon-benchmark":  "libor_usd_quarterly" ,
                "coupon-rate":  "2.14" ,
                "coupon-type":  "floating" ,
                "cusip":  "71647NAE9" ,
                "face-value": 1000 ,
                "id":  "521bd4375a67d23338b2462152cd9d331cc9bc652e8974681a1838d5df0ff0e9" ,
                "isin":  "US71647NAE94" ,
                "issuer":  "PETBRA" ,
                "maturity-date":  "01/15/2019" ,
                "object-id":  "521bd4375a67d23338b2462152cd9d331cc9bc652e8974681a1838d5df0ff0e9" ,
                "object-type":  "bond" ,
                "ref-count": 0
            },
            {
                "amount-outstanding":  "42671000000" ,
                "corporate-debt-ratings": {
                    "Fitch":  "AAA" ,
                    "Moodys":  "AAA" ,
                    "S&P":  "AA+"
                } ,
                "coupon-rate":  "1.375" ,
                "coupon-type":  "fixed" ,
                "cusip":  "912828R77" ,
                "face-value": 1000 ,
                "first-settlement-date":  "xx" ,
                "id":  "28dcccf6be33bd100b5d74efb51c41c02d5e824da9b4269c61b64dfa334cd14e" ,
                "isin":  "US912828R770" ,
                "issuer":  "T" ,
                "maturity-date":  "20210531" ,
                "object-id":  "28dcccf6be33bd100b5d74efb51c41c02d5e824da9b4269c61b64dfa334cd14e" ,
                "object-type":  "bond" ,
                "ref-count": 0
            },
            {
                "amount-outstanding":  "30392000000" ,
                "corporate-debt-ratings": {
                    "Fitch":  "AAA" ,
                    "Moodys":  "AAA" ,
                    "S&P":  "AA+"
                } ,
                "coupon-rate":  "2.5" ,
                "coupon-type":  "fixed" ,
                "cusip":  "912810RS9" ,
                "face-value": 1000 ,
                "first-settlement-date":  "xx" ,
                "id":  "e3616ce5b73184f3612738665f8c78fd0c7ef065cb835178ef7256f18f074a6d" ,
                "isin":  "US912810RS96" ,
                "issuer":  "T" ,
                "maturity-date":  "20460515" ,
                "object-id":  "e3616ce5b73184f3612738665f8c78fd0c7ef065cb835178ef7256f18f074a6d" ,
                "object-type":  "bond" ,
                "ref-count": 0
            },
            {
                "amount-outstanding":  "48201000000" ,
                "corporate-debt-ratings": {
                    "Fitch":  "AAA" ,
                    "Moodys":  "AAA" ,
                    "S&P":  "AA+"
                } ,
                "coupon-rate":  "1.625" ,
                "coupon-type":  "fixed" ,
                "cusip":  "912828R36" ,
                "face-value": 1000 ,
                "first-settlement-date":  "xx" ,
                "id":  "d1bf29f0caf6ef343c0fa01b09aefa26df48b61260b882b470d37e213c944897" ,
                "isin":  "US912828R366" ,
                "issuer":  "T" ,
                "maturity-date":  "20260515" ,
                "object-id":  "d1bf29f0caf6ef343c0fa01b09aefa26df48b61260b882b470d37e213c944897" ,
                "object-type":  "bond" ,
                "ref-count": 0
            },
            {
                "amount-outstanding":  "2250000000" ,
                "corporate-debt-ratings": {
                    "Fitch":  "BBB" ,
                    "Moodys":  "Ba3" ,
                    "S&P":  "BBB-"
                } ,
                "coupon-rate":  "4.375" ,
                "coupon-type":  "fixed" ,
                "cusip":  "91911TAM5" ,
                "face-value": 1000 ,
                "first-settlement-date":  "01/11/2012" ,
                "id":  "cd8e729436f26bdd3d8068f57332895d434e9a396e6f786ecfaf1b6cc74d09c3" ,
                "isin":  "US91911TAM53" ,
                "issuer":  "VALEBZ" ,
                "maturity-date":  "01/11/2022" ,
                "object-id":  "cd8e729436f26bdd3d8068f57332895d434e9a396e6f786ecfaf1b6cc74d09c3" ,
                "object-type":  "bond" ,
                "ref-count": 0
            },
        ])
        .then(connector.thenExec(db => db.table('transactions').insert([
            {
                "Dependencies": [ ],
                "InBlock":  "5fe5d88e4853954a" ,
                "Nonce": 1470256054 ,
                "Signature":  "IKm4us6e+fniYYjGDbArDZBsOM1YHxRUO5Ce1xLGK/QjYCpaMS8zV6i5N5uFRyuGSs7WkQSlkgx10efHvAPc7/g=" ,
                "Status": 2 ,
                "TransactionType":  "/BondTransaction" ,
                "Updates": [
                    {
                        "AmountOutstanding": 100000000 ,
                        "CorporateDebtRatings": {
                            "Moody's":  "AA"
                        } ,
                        "CouponFrequency":  "Quarterly" ,
                        "CouponRate": 4.5 ,
                        "CouponType":  "Fixed" ,
                        "Cusip":  "" ,
                        "FaceValue": 1000 ,
                        "FirstCouponDate":  "01/01/2017" ,
                        "Isin":  "GB0002634946" ,
                        "Issuer":  "T" ,
                        "MaturityDate":  "01/01/2020" ,
                        "ObjectId":  "e9bc6150db20f52243e5a4233f326fd5452fe6b12286420a2a573c1f42345a59" ,
                        "UpdateType":  "CreateBond"
                    }
                ] ,
                "blockid":  "840ea83ed130fff5" ,
                "created": 1470256055454 ,
                "creator": null ,
                "creator-id": '34968a4520a26e675b0bc9df436e5574c92464a373729537fca684daf9c2f73e',
                "id":  "ec236f44c3aeaa53"
            }
        ])))
        .then(done)
        .catch(helpers.failAsync(done));
    });

    describe('bonds()', () => {

        it('should fetch all bonds by default', (done) =>
            bondService.bonds('34968a4520a26e675b0bc9df436e5574c92464a373729537fca684daf9c2f73e')
                .then(bonds => {
                    expect(bonds.count).toBe(7);
                    expect(bonds.data.length).toBe(7);
                })
                .then(done)
                .catch(helpers.failAsync(done)));


        it('should fetch all bonds with an empty search term', (done) =>
            bondService.bonds('34968a4520a26e675b0bc9df436e5574c92464a373729537fca684daf9c2f73e', '')
                .then(bonds => {
                    expect(bonds.count).toBe(7);
                    expect(bonds.data.length).toBe(7);
                })
                .then(done)
                .catch(helpers.failAsync(done)));

        it('should search by isin', (done) =>
            bondService.bonds('34968a4520a26e675b0bc9df436e5574c92464a373729537fca684daf9c2f73e', 'US035242AP13')
                .then(bonds => {
                    expect(bonds.count).toBe(1);
                    expect(bonds.data.length).toBe(1);
                    expect(bonds.data[0].id)
                        .toBe('bfc8ba09734e4fb46d603b0fa058e6ea4b25778a4910afb1b3c9eb660fa280ee');
                })
                .then(done)
                .catch(helpers.failAsync(done)));

        it('should search by cusip', (done) =>
            bondService.bonds('34968a4520a26e675b0bc9df436e5574c92464a373729537fca684daf9c2f73e', '91911TAM5')
                .then(bonds => {
                    expect(bonds.count).toBe(1);
                    expect(bonds.data.length).toBe(1);
                    expect(bonds.data[0].id)
                        .toBe('cd8e729436f26bdd3d8068f57332895d434e9a396e6f786ecfaf1b6cc74d09c3');
                })
                .then(done)
                .catch(helpers.failAsync(done)));

        it('should search by issuer', (done) =>
            bondService.bonds('34968a4520a26e675b0bc9df436e5574c92464a373729537fca684daf9c2f73e', 'T')
                .then(bonds => {
                    expect(bonds.count).toBe(3);
                    expect(bonds.data.length).toBe(3);
                    expect(_.pluck(bonds.data, 'id')).toEqual([
                        'd1bf29f0caf6ef343c0fa01b09aefa26df48b61260b882b470d37e213c944897',
                        '28dcccf6be33bd100b5d74efb51c41c02d5e824da9b4269c61b64dfa334cd14e',
                        'e3616ce5b73184f3612738665f8c78fd0c7ef065cb835178ef7256f18f074a6d',
                    ]);
                })
                .then(done)
                .catch(helpers.failAsync(done)));

        it('should limit and page results', (done) =>
            bondService.bonds('34968a4520a26e675b0bc9df436e5574c92464a373729537fca684daf9c2f73e',
                              null,
                              {limit: 4, page: 0})
                .then(bonds => {
                    expect(bonds.count).toBe(7);
                    expect(bonds.data.length).toBe(4);
                    expect(bonds.hasMore).toBeTruthy();
                    expect(bonds.nextPage).toBe(1);
                })
                .then(done)
                .catch(helpers.failAsync(done)));

        describe('fetching pending bonds', () => {

            beforeAll((done) =>
                connector.exec(db => db.table('transactions').insert([
                        {
                            "Dependencies": [ ],
                            "InBlock":  "5fe5d88e4853954a" ,
                            "Nonce": 1470256054 ,
                            "Signature":  "IKm4us6e+fniYYjGDbArDZBsOM1YHxRUO5Ce1xLGK/QjYCpaMS8zV6i5N5uFRyuGSs7WkQSlkgx10efHvAPc7/g=" ,
                            "Status": 1 ,
                            "TransactionType":  "/BondTransaction" ,
                            "Updates": [
                            {
                                "AmountOutstanding": 100000000 ,
                                "CorporateDebtRatings": {
                                    "Moody's":  "AA"
                                } ,
                                "CouponFrequency":  "Quarterly" ,
                                "CouponRate": 4.5 ,
                                "CouponType":  "Fixed" ,
                                "FaceValue": 1000 ,
                                "FirstCouponDate":  "01/01/2017" ,
                                "Isin":  "US0002634946" ,
                                "Issuer":  "T" ,
                                "MaturityDate":  "01/01/2020" ,
                                "ObjectId":  "eca0287aac478e8a2c8d107db6ae140865ddb311ae867fbef405ea64bb3a9bc9" ,
                                "UpdateType":  "CreateBond"
                            }
                            ] ,
                            "blockid":  "840ea83ed130fff5" ,
                            "created": 1470256055454 ,
                            "creator": null ,
                            "creator-id": '34968a4520a26e675b0bc9df436e5574c92464a373729537fca684daf9c2f73e',
                            "id":  "ec236f44c3aeaa53"
                        }
                ]))
                .then(done)
                .catch(helpers.failAsync(done)));

            it('should return the pending bond as a bond', (done) =>
                bondService.bonds('34968a4520a26e675b0bc9df436e5574c92464a373729537fca684daf9c2f73e')
                    .then((bonds) => {
                        expect(bonds.count).toBe(8);
                        expect(_.pluck(bonds.data, 'id')).toEqual(jasmine.arrayContaining([
                                'eca0287aac478e8a2c8d107db6ae140865ddb311ae867fbef405ea64bb3a9bc9',
                        ]));
                    })
                    .then(done)
                    .catch(helpers.failAsync(done)));

        });
    });

    describe('bondByBondIdentifier()', () =>  {
        it('should fetch by isin', (done) =>
            bondService.bondByBondIdentifier('US912828R366')
                .then(bond => {
                    expect(bond.id).toBe('d1bf29f0caf6ef343c0fa01b09aefa26df48b61260b882b470d37e213c944897');
                })
                .then(done)
                .catch(helpers.failAsync(done)));

        it('should fetch by cusip', (done) =>
            bondService.bondByBondIdentifier('91911TAM5')
                .then(bond => {
                    expect(bond.id).toBe('cd8e729436f26bdd3d8068f57332895d434e9a396e6f786ecfaf1b6cc74d09c3');
                })
                .then(done)
                .catch(helpers.failAsync(done)));

        it('should return null if none found', (done) =>
            bondService.bondByBondIdentifier("unknown_id")
                .then(bond => {
                    expect(bond).toBe(null);
                })
                .then(done)
                .catch(helpers.failAsync(done)));

    });

    afterEach(done => {
        helpers.cleanBlock('112233')
            .then(connector.thenExec(db => db.table('transactions').delete()))
            .then(done)
            .catch(helpers.failAsync(done));
    });


});
