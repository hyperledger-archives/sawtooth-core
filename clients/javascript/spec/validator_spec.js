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
let chai = require('chai');
let assert = chai.assert;

let sinon = require('sinon');
let {PassThrough} = require('stream');
let http = require('http');

let validator = require('../lib/validator');
let signed_object = require('../lib/signed_object');
let cbor = require('cbor');

const _respondWith = (fixture, code, body) => {
    let response = new PassThrough();
    response.headers = {};
    if(body && Buffer.isBuffer(body)) {
        response.headers['content-type'] = 'application/cbor';
    } else {
        response.headers['content-type'] = 'application/json';
    }
    response.statusCode = code;
    if(body && Buffer.isBuffer(body)) {
        response.write(body);
    } else if(body) {
        response.write(JSON.stringify(body));
    }
    response.end();

    let request = new PassThrough();

    fixture.request.callsArgWith(1, response)
                   .returns(request);
};

const _getReqestArgs = (fixture, callIndex = 0) =>
    fixture.request.args[callIndex][0]; 

const _assertGet = (fixture, uri) =>
        assert.deepEqual({
            hostname: 'localhost',
            port: 1234,
            path: uri,
            headers: {
                'Accept': 'application/json',
            }
        },
        _getReqestArgs(fixture));

describe('validator', () => {
    let fixture = {};
    beforeEach(() => {
        fixture.request = sinon.stub(http, 'request');
    });

    afterEach(() => {
        http.request.restore();
        fixture.request = null;
    });

    describe('ValidatorClient', () => {

        beforeEach(() => {
            fixture.validator = new validator.ValidatorClient('localhost', 1234);
        });

        afterEach(() => {
            fixture.validator = null;
        });

        describe('getStores()', () => {

            it('should return the list of stores', (done) => {
                _respondWith(fixture, 200, ['/store1', '/store2']);

                let promise = fixture.validator.getStores();
                _assertGet(fixture, '/store');

                promise.then((stores) => {
                    assert.deepEqual(['/store1', '/store2'],
                            stores);
                    done();
                })
                .catch(done);

            });

            it('should return null on a 404', (done) => {
                _respondWith(fixture, 404);

                fixture.validator
                    .getStores()
                    .then((res) => {
                        assert.isNull(res);
                    })
                    .then(done)
                    .catch(done);
            });

            it('should return a failing promise on a bad response', (done) => {

                _respondWith(fixture, 500);

                fixture.validator
                    .getStores()
                    .then((e) => {
                        assert.isNotOk(e);
                    })
                    .catch((e) => {
                        assert.instanceOf(e, Error);
                        assert.equal('Invalid Request: 500', e.message);
                    })
                    .then(done)
                    .catch(done);
            });

        });

        describe('getStore()', () => {
            it('should return the list of keys', (done) => {
                _respondWith(fixture, 200, ['abcdefg', '123456']);

                let promise = fixture.validator.getStore('/my_store');

                _assertGet(fixture, '/store/my_store');

                promise.then(keys => {
                    assert.deepEqual(['abcdefg', '123456'], keys);
                })
                .then(done)
                .catch(done);
            });

            it('should take a store name with out leading "/"', (done) => {
                _respondWith(fixture, 200, ['abcdefg', '123456']);

                let promise = fixture.validator.getStore('my_store');

                _assertGet(fixture, '/store/my_store');

                promise.then(keys => {
                    assert.deepEqual(['abcdefg', '123456'], keys);
                })
                .then(done)
                .catch(done);
            });

            it('should return null on a 404', (done) => {
                _respondWith(fixture, 404);

                fixture.validator
                    .getStore('/something')
                    .then((res) => {
                        assert.isNull(res);
                    })
                    .then(done)
                    .catch(done);
            });

            it('should return a failng promise on a bad response', (done) => {
                _respondWith(fixture, 500);
                fixture.validator
                    .getStore('/my_store')
                    .then((e) => {
                        assert.isNotOk(e);
                    })
                    .catch((e) => {
                        assert.instanceOf(e, Error);
                        assert.equal('Invalid Request: 500', e.message);
                    })
                    .then(done)
                    .catch(done);
            });

        });

        describe('getStoreObjects()', () => {

            it('should return the list of objects', (done) => {
                _respondWith(fixture, 200, [
                    {
                        id: 'abcdefg',
                        x: 1,
                        y: 2
                    },
                    {
                        id: '123456',
                        x: 3,
                        y: 1,
                    }
                ]);

                let promise = fixture.validator.getStoreObjects('/my_store');

                _assertGet(fixture, '/store/my_store/*');

                promise.then(keys => {
                    assert.deepEqual([
                        {
                            id: 'abcdefg',
                            x: 1,
                            y: 2
                        },
                        {
                            id: '123456',
                            x: 3,
                            y: 1,
                        }
                    ], keys);
                })
                .then(done)
                .catch(done);
            });

            it('should send blockId', (done) => {
                _respondWith(fixture, 200, []);

                fixture.validator.getStoreObjects('/my_store', {blockId: '3ec81a83cede0739'})
                       .then(() => {
                           _assertGet(fixture, '/store/my_store/*?blockid=3ec81a83cede0739');
                       })
                       .then(done)
                       .catch(done);
            });

            it('should send delta flag', (done) => {
                _respondWith(fixture, 200, []);

                fixture.validator.getStoreObjects('/my_store', {delta: true})
                       .then(() => {
                           _assertGet(fixture, '/store/my_store/*?delta=1');
                       })
                       .then(done)
                       .catch(done);
            });

            it('should send both blockId and delta flag', (done) => {
                _respondWith(fixture, 200, []);

                fixture.validator.getStoreObjects('/my_store', {
                    delta: true,
                    blockId: '3ec81a83cede0739',
                })
                .then(() => {
                    _assertGet(fixture, '/store/my_store/*?blockid=3ec81a83cede0739&delta=1');
                })
                .then(done)
                .catch(done);
            });

            it('should return null on a 404', (done) => {
                _respondWith(fixture, 404);

                fixture.validator
                    .getStoreObjects('/something')
                    .then((res) => {
                        assert.isNull(res);
                    })
                    .then(done)
                    .catch(done);
            });

            it('should return a failng promise on a bad response', (done) => {
                _respondWith(fixture, 500);
                fixture.validator
                    .getStoreObjects('/my_store')
                    .then((e) => {
                        assert.isNotOk(e);
                    })
                    .catch((e) => {
                        assert.instanceOf(e, Error);
                        assert.equal('Invalid Request: 500', e.message);
                    })
                    .then(done)
                    .catch(done);
            });
        });

        describe('getStoreObject()', () => {

            it('should return the list of objects', (done) => {
                _respondWith(fixture, 200, {
                        id: 'abcdefg',
                        x: 1,
                        y: 2
                    });

                let promise = fixture.validator.getStoreObject('/my_store', 'abcdefg');

                _assertGet(fixture, '/store/my_store/abcdefg');

                promise.then(keys => {
                    assert.deepEqual({
                            id: 'abcdefg',
                            x: 1,
                            y: 2
                        }, keys);
                })
                .then(done)
                .catch(done);
            });

            it('should return null on a 404', (done) => {
                _respondWith(fixture, 404);

                fixture.validator
                    .getStoreObject('/my_store','someunknown')
                    .then((res) => {
                        assert.isNull(res);
                    })
                    .then(done)
                    .catch(done);
            });

            it('should return a failng promise on a bad response', (done) => {
                _respondWith(fixture, 500);
                fixture.validator
                    .getStoreObject('/my_store', 'foo')
                    .then((e) => {
                        assert.isNotOk(e);
                    })
                    .catch((e) => {
                        assert.instanceOf(e, Error);
                        assert.equal('Invalid Request: 500', e.message);
                    })
                    .then(done)
                    .catch(done);
            });
        });


        describe('sendTransaction()', () => {

            it('should send a transaction', (done) => {
                _respondWith(fixture, 200, cbor.encode({
                    Transaction: {
                        Signature: 'ING9fBk6tbrEmAGOXvKYpAhQbl4PKpJxZSJ0b9z2yowMFRviZRZf1IfxDNEMs5z71AzYfObrznqHDyqMgClO6FE=',
                    }
                }));

                let cborTxn = cbor.encode(signed_object.createSignableObj({a: 1, b: 2}).toJS());
                let promise = fixture.validator.sendTransaction('/my_txn_family', cborTxn);

                assert.deepEqual({
                    hostname: 'localhost',
                    port: 1234,
                    path: '/my_txn_family',
                    method: 'POST',
                    headers: {
                        'Content-Length': cborTxn.length,
                        'Content-Type': 'application/cbor',
                    }
                },
                _getReqestArgs(fixture));  

                promise.then((txnId) => {
                    assert.equal('080299fa5038fe58', txnId);
                })
                .then(done)
                .catch(done);
            });

            it('should send a string transaction as json', (done) => {
                _respondWith(fixture, 200, {
                    Transaction: {
                        Signature: 'H2K8jRxEmNz8MRHmuoKFwr7rjgTG1Ro71yu3XZlpJ9kuVkVsm0hFzOiI1x0IQcT4eugeQ7V+lFB1txfpPbhDB9U=',
                    }
                });
                let txnStr = "{x: 1, y: 2}";
                let promise = fixture.validator.sendTransaction('/my_txn_family', txnStr);

                assert.deepEqual({
                    hostname: 'localhost',
                    port: 1234,
                    path: '/my_txn_family',
                    method: 'POST',
                    headers: {
                        'Content-Length': txnStr.length,
                        'Content-Type': 'application/json',
                    }
                },
                _getReqestArgs(fixture));  

                promise.then((txnId) => {
                    assert.equal('3ec81a83cede0739', txnId);
                })
                .then(done)
                .catch(done);
            });

            it('should parse an error if one is in the response', (done) => {
                _respondWith(fixture, 400, 'bad id: must be 10 chars');
                fixture.validator
                    .sendTransaction('/my_txn_family', '{x: 1, y: 2}')
                    .then((e) => {
                        assert.isNotOk(e);
                    })
                    .catch((e) => {
                       assert.deepEqual({
                           statusCode: 400,
                           errorTypeMessage: 'bad id',
                           errorMessage: 'must be 10 chars',
                       }, e);
                    })
                    .then(done)
                    .catch(done);
            });

            it('should respond with an error object if one is in the response', (done) => {
                _respondWith(fixture, 400, {
                    error: "invalid signature",
                    errorType: "InvalidTransactionError",
                    status: 400
                });

                fixture.validator
                       .sendTransaction('/my_txn_family', '{x: 1, y:2}')
                       .then((e) => {
                           assert.isNotOk(e);
                       })
                       .catch((e) => {
                           assert.deepEqual({
                               error: "invalid signature",
                               errorType: "InvalidTransactionError",
                               statusCode: 400
                           }, e);
                       })
                       .then(done)
                       .catch(done);
            });

            it('should throw an exception on a badly formatted request response', (done) => {
                _respondWith(fixture, 400, 'unable to decode incoming request');
                fixture.validator
                    .sendTransaction('/my_txn_family', '{x: 1, y: 2')
                    .then((e) => {
                        assert.isNotOk(e);
                    })
                    .catch((e) => {
                        assert.instanceOf(e, Error);
                        assert.equal('Invalid Request: 400', e.message);
                    })
                    .then(done)
                    .catch(done);
            });

            it('should throw an exception on a badly formatted request response: old version', (done) => {
                _respondWith(fixture, 400, 'unabled to decode incoming request');
                fixture.validator
                    .sendTransaction('/my_txn_family', '{x: 1, y: 2')
                    .then((e) => {
                        assert.isNotOk(e);
                    })
                    .catch((e) => {
                        assert.instanceOf(e, Error);
                        assert.equal('Invalid Request: 400', e.message);
                    })
                    .then(done)
                    .catch(done);
            });
        });

        describe('getBlockList()', () => {

            it('should retrieve the list of blocks', (done) => {
                _respondWith(fixture, 200, [
                        "353c1562c1b2ce25"
                ]);

                let promise = fixture.validator.getBlockList();

                _assertGet(fixture, '/block');

                promise.then((blockIds) => {
                        assert.deepEqual([
                            "353c1562c1b2ce25"
                        ], blockIds);
                    })
                    .then(done)
                    .catch(done);
            });

            it('should limit the list by count', (done) => {
                _respondWith(fixture, 200, [
                    "c8aca08fcb4511db",
                    "bfc2c7fe07b3cfb5",
                    "4cb539ee7f7f1b63",
                    "0c4c32a0ba5196f5",
                    "c4f20c558978e0d1"
                ]);

                let promise = fixture.validator.getBlockList({count: 5});

                _assertGet(fixture, '/block?blockcount=5');

                promise.then((blockIds) => {
                        assert.deepEqual([
                            "c8aca08fcb4511db",
                            "bfc2c7fe07b3cfb5",
                            "4cb539ee7f7f1b63",
                            "0c4c32a0ba5196f5",
                            "c4f20c558978e0d1"
                        ], blockIds);
                    })
                    .then(done)
                    .catch(done);
            });
        });

        describe('getBlock()', () => {
            it('should retrieve info about the block', (done) => {
                _respondWith(fixture, 200, {
                    BlockNum: 0,
                    Identifier: "353c1562c1b2ce25",
                    PreviousBlockID: "0000000000000000",
                    Signature: "G64l3yMwGVk2/JlHux2zchN5ClR19cTYo8e0Ey49qt1e2avJDxCNmLHYdfHBEdwrlcqC0ZN6wfwAT1+Cft+aUkY=",
                    TransactionBlockType: "/Poet/PoetTransactionBlock",
                    TransactionIDs: [ ],
                    WaitCertificate: {
                        SerializedCert: "For The Sake of brevity, this is omitted",
                        Signature: "biq24geaer6vqki3782ns7a3d4hbb9qdqfv5yesr8j3dtkvuzb2576zx2i53husmjqmbfafnmaf8wyeb83fqicb9memzi6chvyp6xga"
                    }
                });

                let promise = fixture.validator.getBlock('353c1562c1b2ce25');

                _assertGet(fixture, '/block/353c1562c1b2ce25');

                promise.then((blockInfo) => {
                    assert.deepEqual({
                        BlockNum: 0,
                        Identifier: "353c1562c1b2ce25",
                        PreviousBlockID: "0000000000000000",
                        Signature: "G64l3yMwGVk2/JlHux2zchN5ClR19cTYo8e0Ey49qt1e2avJDxCNmLHYdfHBEdwrlcqC0ZN6wfwAT1+Cft+aUkY=",
                        TransactionBlockType: "/Poet/PoetTransactionBlock",
                        TransactionIDs: [ ],
                        WaitCertificate: {
                            SerializedCert: "For The Sake of brevity, this is omitted",
                            Signature: "biq24geaer6vqki3782ns7a3d4hbb9qdqfv5yesr8j3dtkvuzb2576zx2i53husmjqmbfafnmaf8wyeb83fqicb9memzi6chvyp6xga"
                        }
                    }, blockInfo);
                })
                .then(done)
                .catch(done);

            });

            it('should retrieve just a specified field, when specified', (done) => {
                _respondWith(fixture, 200, "/Poet/PoetTransactionBlock");

                let promise = fixture.validator.getBlock('353c1562c1b2ce25', {
                    field: 'TransactionBlockType'
                });

                _assertGet(fixture, '/block/353c1562c1b2ce25/TransactionBlockType');

                promise.then((fieldValue) => {
                    assert.equal(fieldValue, '/Poet/PoetTransactionBlock');
                })
                .then(done)
                .catch(done);
            });

            it('should return null for an unknown block', (done) => {
                _respondWith(fixture, 404);
                let promise = fixture.validator.getBlock('someunknown');

                _assertGet(fixture, '/block/someunknown');

                promise.then((block) => {
                    assert.isNull(block);
                })
                .then(done)
                .catch(done);
            });

            it('should return a failng promise on a bad response', (done) => {
                _respondWith(fixture, 500);
                fixture.validator
                    .getBlock('bad')
                    .then((e) => {
                        assert.isNotOk(e);
                    })
                    .catch((e) => {
                        assert.instanceOf(e, Error);
                        assert.equal('Invalid Request: 500', e.message);
                    })
                    .then(done)
                    .catch(done);
            });

            it('should throw an exception on a null blockid', (done) => {
                try {
                    fixture.validator.getBlock(null).then(done);
                    assert.isNotOk(true, 'No exception was thrown');
                } catch(e) {
                    assert.isNotNull(e);
                    done();
                }
            });
        });

        describe('getTransactions()', () => {
            it('should return a list of transactions', (done) => {
                _respondWith(fixture, 200, [
                    "7db1724f1fc98e5a",
                    "dc82344c96d4140a",
                    "24b2027d3dda73a8",
                    "632ffa123502c92b",
                    "9682a0168a54dc9c",
                    "1c7d243c0e1ee747",
                    "f6c0e3c17b353ac4",
                    "b9eb527bd0b538e7"
                ]);

                let promise = fixture.validator.getTransactions();

                _assertGet(fixture, '/transaction');

                promise.then((transactionIds) => {
                    assert.deepEqual(transactionIds, [
                        "7db1724f1fc98e5a",
                        "dc82344c96d4140a",
                        "24b2027d3dda73a8",
                        "632ffa123502c92b",
                        "9682a0168a54dc9c",
                        "1c7d243c0e1ee747",
                        "f6c0e3c17b353ac4",
                        "b9eb527bd0b538e7"
                    ]);
                })
                .then(done)
                .catch(done);

            });

            it('should return a limit the list of transactions by count', (done) => {
                _respondWith(fixture, 200, [
                    "7db1724f1fc98e5a",
                    "dc82344c96d4140a",
                ]);

                let promise = fixture.validator.getTransactions({count: 2});

                _assertGet(fixture, '/transaction?blockcount=2');

                promise.then((transactionIds) => {
                    assert.deepEqual(transactionIds, [
                        "7db1724f1fc98e5a",
                        "dc82344c96d4140a",
                    ]);
                })
                .then(done)
                .catch(done);

            });

            it('should return a failng promise on a bad response', (done) => {
                _respondWith(fixture, 500);
                fixture.validator
                    .getTransactions()
                    .then((e) => {
                        assert.isNotOk(e);
                    })
                    .catch((e) => {
                        assert.instanceOf(e, Error);
                        assert.equal('Invalid Request: 500', e.message);
                    })
                    .then(done)
                    .catch(done);
            });
        });

        describe('getTransaction()', () => {
            it('should return the full transaction responose', (done) => {
                _respondWith(fixture, 200, {
                    Dependencies: [ ],
                    Identifier: "b9eb527bd0b538e7",
                    InBlock: "c8aca08fcb4511db",
                    Nonce: 1473889440.044142,
                    Signature: "HGnWzKq1ZjPLxKHNGdWz6SFduyk5nVfmt/rIsptPy5B2HSw0mLdp9LIjrz5gMYlp4cBdlKhon8gVvFzWnQ4rzTY=",
                    Status: 2,
                    TransactionType: "/TestFamily",
                    Updates: [
                        {
                            UpdateType: "TestUpdate",
                            ObjectId: '12345678',
                            Name: 'Testing'
                        }
                    ]
                });

                let promise = fixture.validator.getTransaction('b9eb527bd0b538e7');

                _assertGet(fixture, '/transaction/b9eb527bd0b538e7');

                promise.then(txn => {
                    assert.deepEqual(txn, {
                        Dependencies: [ ],
                        Identifier: "b9eb527bd0b538e7",
                        InBlock: "c8aca08fcb4511db",
                        Nonce: 1473889440.044142,
                        Signature: "HGnWzKq1ZjPLxKHNGdWz6SFduyk5nVfmt/rIsptPy5B2HSw0mLdp9LIjrz5gMYlp4cBdlKhon8gVvFzWnQ4rzTY=",
                        Status: 2,
                        TransactionType: "/TestFamily",
                        Updates: [
                            {
                                UpdateType: "TestUpdate",
                                ObjectId: '12345678',
                                Name: 'Testing'
                            }
                        ]
                    });
                })
                .then(done)
                .catch(done);
            });

            it('should return just a field value', (done) => {
                _respondWith(fixture, 200, 2);

                let promise = fixture.validator.getTransaction('b9eb527bd0b538e7', {
                    field: 'Status'
                });

                _assertGet(fixture, '/transaction/b9eb527bd0b538e7/Status');

                promise.then(status => {
                    assert.equal(status, 2);
                })
                .then(done)
                .catch(done);
            });

            it('should return null for an unknown transaction', (done) => {
                _respondWith(fixture, 404);
                let promise = fixture.validator.getTransaction('someunknown');

                _assertGet(fixture, '/transaction/someunknown');

                promise.then((transaction) => {
                    assert.isNull(transaction);
                })
                .then(done)
                .catch(done);
            });

            it('should return a failng promise on a bad response', (done) => {
                _respondWith(fixture, 500);
                fixture.validator
                    .getTransaction('bad')
                    .then((e) => {
                        assert.isNotOk(e);
                    })
                    .catch((e) => {
                        assert.instanceOf(e, Error);
                        assert.equal('Invalid Request: 500', e.message);
                    })
                    .then(done)
                    .catch(done);
            });

        });

        describe('getStatus()', () => {
            it('should return the validator status', (done) => {
                _respondWith(fixture, 200, {
                    AllPeers: [ ],
                    Blacklist: [ ],
                    Host: "0.0.0.0",
                    HttpPort: null,
                    Name: "base000",
                    NodeIdentifier: "1DqZNkmCgjxZwL9y1FgikyrMQepNSpmszz",
                    Peers: [ ],
                    Port: 5500,
                    Status: "started"
                });

                let promise = fixture.validator.getStatus();

                _assertGet(fixture, '/status');

                promise.then(statusInfo => {
                    assert.deepEqual(statusInfo, {
                        AllPeers: [ ],
                        Blacklist: [ ],
                        Host: "0.0.0.0",
                        HttpPort: null,
                        Name: "base000",
                        NodeIdentifier: "1DqZNkmCgjxZwL9y1FgikyrMQepNSpmszz",
                        Peers: [ ],
                        Port: 5500,
                        Status: "started"
                    });
                })
                .then(done)
                .catch(done);
            });

            it('should return a failng promise on a bad response', (done) => {
                _respondWith(fixture, 500);
                fixture.validator
                    .getStatus()
                    .then((e) => {
                        assert.isNotOk(e);
                    })
                    .catch((e) => {
                        assert.instanceOf(e, Error);
                        assert.equal('Invalid Request: 500', e.message);
                    })
                    .then(done)
                    .catch(done);
            });

        });
    });
});
