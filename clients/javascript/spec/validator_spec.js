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

var sinon = require('sinon');
var {PassThrough} = require('stream');
var http = require('http');

var validator = require('../lib/validator');
var signed_object = require('../lib/signed_object');
var cbor = require('cbor');

const _respondWith = (fixture, code, body) => {
    var response = new PassThrough();
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

    var request = new PassThrough();

    fixture.request.callsArgWith(1, response)
                   .returns(request);
};

const _getReqestArgs = (fixture, callIndex = 0) =>
    fixture.request.args[callIndex][0]; 



describe('validator', () => {
    var fixture = {};
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

                var promise = fixture.validator.getStores();
                assert.deepEqual({
                    hostname: 'localhost',
                    port: 1234,
                    path: '/store',
                    headers: {
                        'Accept': 'application/json',
                    }
                },
                _getReqestArgs(fixture));

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

                assert.deepEqual({
                    hostname: 'localhost',
                    port: 1234,
                    path: '/store/my_store',
                    headers: {
                      'Accept': 'application/json',
                    }
                },
                _getReqestArgs(fixture));  

                promise.then(keys => {
                    assert.deepEqual(['abcdefg', '123456'], keys);
                })
                .then(done)
                .catch(done);
            });

            it('should take a store name with out leading "/"', (done) => {
                _respondWith(fixture, 200, ['abcdefg', '123456']);

                let promise = fixture.validator.getStore('my_store');

                assert.deepEqual({
                    hostname: 'localhost',
                    port: 1234,
                    path: '/store/my_store',
                    headers: {
                      'Accept': 'application/json',
                    }
                },
                _getReqestArgs(fixture));  

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

                assert.deepEqual({
                    hostname: 'localhost',
                    port: 1234,
                    path: '/store/my_store/*',
                    headers: {
                      'Accept': 'application/json',
                    }
                },
                _getReqestArgs(fixture));  

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

                assert.deepEqual({
                    hostname: 'localhost',
                    port: 1234,
                    path: '/store/my_store/abcdefg',
                    headers: {
                      'Accept': 'application/json',
                    }
                },
                _getReqestArgs(fixture));  

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
    
    });
});
