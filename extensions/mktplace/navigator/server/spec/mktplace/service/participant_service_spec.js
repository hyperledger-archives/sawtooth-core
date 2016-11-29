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

var helpers = require('../../support/helpers');

var connector = require('../../../lib/sawtooth/model/db_connector');
var participantService = require('../../../lib/mktplace/service/participant_service');


describe('ParticipantService', () => {

    beforeEach((done) => {
        helpers.createBlock('12345', [
                {
                    "id" : "0048b49467ce69f1",
                    "object-type" : "Participant",
                    "description" : "",
                    "fqname" : "//participant76",
                    "address" : "1Fn7MGHMQMjLRgMCqmQXdmRfGXDYSyMfJh",
                    "name" : "participant76"
                },
                {
                    "id" : "2f301284f9eff603",
                    "account" : "569501fe511382aa",
                    "asset" : "d235fa3207d73f17",
                    "count" : 10000,
                    "creator" : "0048b49467ce69f1",
                    "description" : "",
                    "name" : "/holding/currency/mikel",
                    "object-type" : "Holding",
                    "fqname" : "//participant100/holding/currency/mikel"
                },
                {
                    "id" : "10dadf6340a1fb14",
                    "account" : "569501fe511382aa",
                    "asset" : "1728914b36b01117",
                    "count" : 100,
                    "creator" : "0048b49467ce69f1",
                    "description" : "",
                    "name" : "/holding/teamstock/east8",
                    "object-type" : "Holding",
                    "fqname" : "//participant100/holding/teamstock/east8"
                },
                {
                    "id" : "15ca4fd8fc21d1e2",
                    "account" : "569501fe511382aa",
                    "asset" : "5090dc5b006e92a8",
                    "count" : 100,
                    "creator" : "0048b49467ce69f1",
                    "description" : "",
                    "name" : "/holding/teamstock/east5",
                    "object-type" : "Holding",
                    "fqname" : "//participant100/holding/teamstock/east5"
                },
                {
                    "id" : "174d299c8cf03ce9",
                    "account" : "569501fe511382aa",
                    "asset" : "fbb1c86238287e9a",
                    "count" : 100,
                    "creator" : "0048b49467ce69f1",
                    "description" : "",
                    "name" : "/holding/teamstock/south10",
                    "object-type" : "Holding",
                    "fqname" : "//participant100/holding/teamstock/south10"
                },
            ])
            .then(connector.thenExec(db  => db.table('transactions').insert([
                {
                    "id" : "0048b49467ce69f1",
                    "Status": 1,
                    "created": 1461965880000,
                    'ledgerId': '0048b49467ce69f1',
                    'creator': null,
                    'blockid': 'c347a340c65b8fec',
                    'Dependencies':  [],
                    'Nonce': 1461965000,
                    "Updates": [{
                        "Name" : "participant76",
                        "Description": "",
                        "UpdateType": "RegisterParticipant",
                    }],
                    "address" : "1Fn7MGHMQMjLRgMCqmQXdmRfGXDYSyMfJh",
                },
                {
                    "id" : "483598d6336eea3f",
                    "Status" : 1,
                    "created" : 1461965881519,
                    "ledgerId" : "483598d6336eea3f",
                    "creator" : null,
                    "blockid" : "c347a340c65b8fec",
                    "Dependencies" : [ ],
                    "Nonce" : 1461965881,
                    "Signature" : "MEQCIHIZuiFnbHNaEQRrz4pe0UnELpbRY/xXWlx9bIgJlSijAiAEbFZzTYmbAZ8O1VFSC+tKPz3NQmErsjKhd8RIeMwwNg==",
                    "TransactionType" : "/MarketPlaceTransaction",
                    "Updates" : [{
                        "Description" : "The Man in Charge",
                        "Name" : "george",
                        "UpdateType" : "RegisterParticipant"
                    }],
                    "address" : "1CzvqLhi85sSAuxgHQ8aQJjEwBJqbyS7ak"
                }
            ])))
            .then(done)
            .catch(helpers.failAsync(done));
    });

    afterEach((done) => {
       helpers.cleanBlock('12345')
            .then(connector.thenExec(db => db.table('transactions').delete()))
            .then(done)
            .catch(helpers.failAsync(done));
    });

    describe('participant', () => {
        
        it('should return the participants money as well as their details', (done) => {
            participantService.participant('0048b49467ce69f1')
                .then(participant => {
                    expect(participant.name).toBe('participant76');
                    expect(participant.holdings.length).toBe(4);
                    expect(participant.holdings).toEqual(jasmine.arrayContaining([
                        {
                            "id" : "2f301284f9eff603",
                            "account" : "569501fe511382aa",
                            "asset" : "d235fa3207d73f17",
                            "asset-settings": null,
                            "count" : 10000,
                            "creator" : "0048b49467ce69f1",
                            "description" : "",
                            "name" : "/holding/currency/mikel",
                            "object-type" : "Holding",
                            "fqname" : "//participant100/holding/currency/mikel"
                        },
                        {
                            "id" : "10dadf6340a1fb14",
                            "account" : "569501fe511382aa",
                            "asset" : "1728914b36b01117",
                            "asset-settings": null,
                            "count" : 100,
                            "creator" : "0048b49467ce69f1",
                            "description" : "",
                            "name" : "/holding/teamstock/east8",
                            "object-type" : "Holding",
                            "fqname" : "//participant100/holding/teamstock/east8"
                        },
                        {
                            "id" : "15ca4fd8fc21d1e2",
                            "account" : "569501fe511382aa",
                            "asset" : "5090dc5b006e92a8",
                            "asset-settings": null,
                            "count" : 100,
                            "creator" : "0048b49467ce69f1",
                            "description" : "",
                            "name" : "/holding/teamstock/east5",
                            "object-type" : "Holding",
                            "fqname" : "//participant100/holding/teamstock/east5"
                        },
                        {
                            "id" : "174d299c8cf03ce9",
                            "account" : "569501fe511382aa",
                            "asset" : "fbb1c86238287e9a",
                            "asset-settings": null,
                            "count" : 100,
                            "creator" : "0048b49467ce69f1",
                            "description" : "",
                            "name" : "/holding/teamstock/south10",
                            "object-type" : "Holding",
                            "fqname" : "//participant100/holding/teamstock/south10"
                        },
                    ]));
                })
                .then(done)
                .catch(helpers.failAsync(done));
        });

        it('should return undefined for an unknown participant', (done) => {

            participantService.participant('some_unknownid')
                .then(participant => {
                        expect(participant).toBeUndefined();
                })
                .then(done)
                .catch(helpers.failAsync(done));
        });
    });

    describe('getByAddress', () => {
        it('should fetch a user by address', (done) => 
            participantService.getByAddress('1Fn7MGHMQMjLRgMCqmQXdmRfGXDYSyMfJh')
                .then(participant => {
                    expect(participant.id).toBe('0048b49467ce69f1');
                })
                .then(done)
                .catch(helpers.failAsync(done)));

        it('should fetch a pending user from transactions', (done) => 
            participantService.getByAddress('1CzvqLhi85sSAuxgHQ8aQJjEwBJqbyS7ak')
                .then(participant => {
                    expect(participant.id).toBe('483598d6336eea3f');
                    expect(participant.name).toBe('george');
                    expect(participant.pending).toBeTruthy();
                })
                .then(done)
                .catch(helpers.failAsync(done)));
    });

    describe('participant', () => {
        it('should fetch a participant by id', (done) =>
            participantService.participant('0048b49467ce69f1')
                .then(participant => {
                    expect(participant.name).toBe('participant76');
                    expect(participant.address).toBeUndefined();
                    expect(participant.pending).toBeFalsy();
                })
                .then(done)
                .catch(helpers.failAsync(done)));

    });
});
