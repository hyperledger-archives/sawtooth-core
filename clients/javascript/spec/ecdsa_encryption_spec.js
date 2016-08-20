/*
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

var chai = require('chai');
var assert = chai.assert;

var cbor = require('cbor');

var ecdsaEncryption = require('../lib/ecdsa_encryption');

const TEST_WIF = 'L5LujASMxJvyoAKHXbLfoguQnPrnzV9JsMK1umMyjpvn2BrVGibJ';

describe('EcdsaEncryption', () => {
    describe('signUpdate()', () => {
        it('should sign an update and produce a transaction object by default', () => {

            let signedTxn =
                ecdsaEncryption.signUpdate(
                        '/my_txn_family',
                        {"x": 1, "y": 2},
                        TEST_WIF);


            assert.equal(signedTxn.__TYPE__, '/my_txn_family');
            assert.isNumber(signedTxn.__NONCE__);
            assert.isNotNull(signedTxn.__SIGNATURE__);

            assert.equal(signedTxn.Transaction.x, 1);
            assert.equal(signedTxn.Transaction.y, 2);
            assert.isNotNull(signedTxn.Transaction.Signature);
        });

        it('should produce output optionally as a json string', () => {

            let signedTxn =
                ecdsaEncryption.signUpdate(
                        '/my_txn_family',
                        {"x": 1, "y": 2},
                        TEST_WIF,
                        {output: "json"});

            assert.isString(signedTxn);
            assert.match(signedTxn,
                    /^{"Transaction":{"Nonce":\d+,"Signature":"\S+","x":1,"y":2},"__NONCE__":\d+,"__SIGNATURE__":"\S+","__TYPE__":"\/my_txn_family"}/);
        });

        it('should produce output optionally as a cbor buffer', (done) => {
            let signedTxn =
                ecdsaEncryption.signUpdate(
                        '/my_txn_family',
                        {"x": 1, "y": 2},
                        TEST_WIF,
                        {output: "cbor"});

            assert.isTrue(Buffer.isBuffer(signedTxn));

            cbor.decodeFirst(signedTxn, (err, unmarshelled) => {
                assert.isNull(err);
                assert.equal(unmarshelled.__TYPE__, '/my_txn_family');
                assert.isNumber(unmarshelled.__NONCE__);
                assert.isNotNull(unmarshelled.__SIGNATURE__);

                assert.equal(unmarshelled.Transaction.x, 1);
                assert.equal(unmarshelled.Transaction.y, 2);
                assert.isNotNull(unmarshelled.Transaction.Signature);
                done();
            });
        });
    });
}); 
