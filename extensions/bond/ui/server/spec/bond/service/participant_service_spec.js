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
var participantService = require('../../../lib/bond/service/participant_service');

describe('ParticipantService', () => {

    beforeEach(done => {
        helpers.createBlock('112233', [
            {
                "creator-id":  "34968a4520a26e675b0bc9df436e5574c92464a373729537fca684daf9c2f73e" ,
                "firm-id": "scgvaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"  ,
                "id":  "34968a4520a26e675b0bc9df436e5574c92464a373729537fca684daf9c2f73e" ,
                "key-id":  "1F9mPDeguDT3u55P44fKoY6tiHGC9ZMkVy" ,
                "object-id":  "34968a4520a26e675b0bc9df436e5574c92464a373729537fca684daf9c2f73e" ,
                "object-type":  "participant" ,
                "username":  "Peter"
            }
        ])
        .then(connector.thenExec(db => db.table('transactions').insert([
            {
                "Dependencies": [ ],
                "InBlock":  "PENDING" ,
                "Nonce": 1468958937 ,
                "Signature":  "ILXSrM9yuoX4DtFnoHbjHCkWvHi/xzYHYk8jv3grLWb5PR5zYw4WrLmFixQEl5HMkPjeyGqtOeN6Fx3wqzY9J8E=" ,
                "Status": 1 ,
                "TransactionType":  "/BondTransaction" ,
                "Updates": [
                    {
                        "FirmId":  "362e98783ad7f328e6b0e75fc8944198d104be4a11f240f4f6bb025e16f1830d" ,
                        "ObjectId":  "feb211712fb97350271e1cdc56bd780ceae653f72663e5e8e23c8293c9499d03" ,
                        "UpdateType":  "CreateParticipant" ,
                        "Username":  "Joe User"
                    }
                ] ,
                "blockid":  "0094c382e6f70800" ,
                "created": 1468958938168 ,
                "creator": null ,
                "id":  "f19b9fc082655b39" ,
                "key-id":  "13czKQB6WXozGu1bpN9Qrmj2bk3qS7J2zy"
            }])))
        .then(done)
        .catch(helpers.failAsync(done));
    });

    afterEach(done => {
        helpers.cleanBlock('112233')
            .then(connector.thenExec(db => db.table('transactions').delete()))
            .then(done)
            .catch(helpers.failAsync(done));
    });

    describe('participantByAddress()', () => {

        it('should return a user by address from the current block', (done) =>
            participantService.participantByAddress('1F9mPDeguDT3u55P44fKoY6tiHGC9ZMkVy')
                .then(participant => {
                    expect(participant.id).toBe('34968a4520a26e675b0bc9df436e5574c92464a373729537fca684daf9c2f73e');
                    expect(participant.username).toBe("Peter");
                })
                .then(done)
                .catch(helpers.failAsync(done)));

        it('should return a pending user by address from the transactions', (done) =>
            participantService.participantByAddress('13czKQB6WXozGu1bpN9Qrmj2bk3qS7J2zy')
                .then(participant => {
                    expect(participant['object-id'])
                        .toBe('feb211712fb97350271e1cdc56bd780ceae653f72663e5e8e23c8293c9499d03');
                    expect(participant.username).toBe('Joe User');
                    expect(participant['firm-id'])
                        .toEqual('362e98783ad7f328e6b0e75fc8944198d104be4a11f240f4f6bb025e16f1830d');
                    expect(participant.pending).toBeTruthy();
                })
                .then(done)
                .catch(helpers.failAsync(done)));

        it('should return undefined if not found', (done) =>
            participantService.participantByAddress('some_unknown_address')
                .then(participant => {
                    expect(participant).toBeUndefined();
                })
                .then(done)
                .catch(helpers.failAsync(done)));

    });

    describe('particpantNamesAndAddresses()', () => {
        it('should return only names and addresses of commited participants', (done) =>
            participantService.participantNamesAndAddresses()
                .then(participants => {
                    expect(participants).toEqual([{
                        'id': '34968a4520a26e675b0bc9df436e5574c92464a373729537fca684daf9c2f73e',
                        'username': 'Peter',
                        'key-id': '1F9mPDeguDT3u55P44fKoY6tiHGC9ZMkVy',
                    }]);
                })
                .then(done)
                .catch(helpers.failAsync(done)));
    });

});
