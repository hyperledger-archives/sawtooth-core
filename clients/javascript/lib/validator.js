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
/**
 * Sawtooth ledger EcdsaEncryption module
 * @module sawtooth/validator
 */
"use strict";

var assert = require('assert');
var http = require('http');
var querystring = require('querystring');
var _ = require('underscore');
var cbor = require('cbor');
var sha256 = require('sha256');
var conv = require('binstring');

var CHUNK_SIZE = 10 * 1024;

function _httpRequest(options, data) {
    return new Promise(function (resolve, reject) {
        var req = http.request(options, function(response) {
            var buffer = new Buffer([]);
            response.on('data', function(chunk) {
                buffer = Buffer.concat([buffer, chunk]);
            });
            response.on('end', function() {

                var p = null;
                if (response.headers['content-type'] === 'application/cbor') {
                    p = cbor.decodeFirst(buffer);
                } else if (response.headers['content-type'] === 'application/json') {
                    p = Promise.resolve(
                            buffer.length > 0 ? JSON.parse(buffer.toString()) : null);
                } else {
                    p = Promise.resolve(buffer.toString());
                }

                p.then(function(body) {
                    if(response.statusCode !== 200 && _.isObject(body)) {
                        reject(_.chain(body)
                                .omit('status')
                                .extend({statusCode: response.statusCode})
                                .value());
                    } else {
                        resolve({
                            body: body,
                            headers: response.headers,
                            statusCode: response.statusCode,
                        });
                    }
                });
            });
        });

        req.on('error', reject);

        if(data) {
            var buffer = Buffer.isBuffer(data) ? data : new Buffer(data);
            var chunk = buffer.slice(0, CHUNK_SIZE);
            var i = 1;
            while(chunk.length > 0) {
                req.write(chunk);
                chunk = buffer.slice(i * CHUNK_SIZE, (i +1) * CHUNK_SIZE);
                i++;
            }
        }

        req.end();
    });
}

function _get(options) {
    return _httpRequest(options);
}

function _post(options, data) {
    return _httpRequest(_.assign(options, {method: 'POST'}), data);
}

function _unwrapResponseBody(result) {
    if(result.statusCode === 200) {
        return result.body;
    }

    // Check for 400, which is the validator's current
    // repsonse for not found, but this may be corrected
    // in the future.
    if(result.statusCode === 404) {
        return null;
    }

    if (result.statusCode === 400) {
        if(!/^unable[d]? to decode incoming request.*/.exec(result.body)) {
            let msgs = result.body.split(":");
            throw ({
                statusCode: 400,
                errorTypeMessage: msgs[0] ? msgs[0].trim() : null,
                errorMessage: msgs.length > 1 ? msgs.slice(1).join(':').trim() : null
            });
        }
    }

    throw new Error("Invalid Request: " + result.statusCode);
}

/**
 * Sends a transaction to a validator at the given host and port.
 * Returns a promise with the resulting transaction id.
 *
 * @param {string} validatorHost
 * @param {number} validatorPort
 * @param (string) txnFamily
 * @param {buffer|string} txn
 * @param {object} [opts]
 * @returns {Promise} a promise for the resulting transaction id
 */
function _sendTransaction(validatorHost, validatorPort, txnFamily, txn, opts) {
    assert(validatorHost, "'validatorHost' must be provided.");
    assert(validatorPort, "'validatorPort' must be provided.");
    assert(txnFamily, "'txnFamily' must be provided.");
    assert(txn, "'txn' must be provided.");

    if (_.isUndefined(opts)) {
        opts = {};
    }

    var contentType = Buffer.isBuffer(txn) ? 'application/cbor' : 'application/json';
    var data = (Buffer.isBuffer(txn) || typeof txn === 'string') ? txn : JSON.stringify(txn);
    var postArgs = {
        hostname: validatorHost,
        port: validatorPort,
        path: txnFamily,
        headers: {
            'Content-Type': contentType,
            'Content-Length': data.length,
        }
    };

    return _post(postArgs, data)
        .then(_unwrapResponseBody)
        .then(function(txn) {
            var sha = sha256(txn.Transaction.Signature, {asBytes: true});
            var hex = conv(sha, {out : 'hex'});
            return hex.toString().substring(0,16);
        });
}

function _patherize(s) {
    return s[0] == '/' ? s : ('/' + s);
}

function _getStoreApi(validatorHost, validatorPort, storeName, key, opts) {
    assert(validatorHost, "'validatorHost' must be provided.");
    assert(validatorPort, "'validatorPort' must be provided.");
    var path = '/store';
    if(!_.isUndefined(storeName) && storeName !== null) {
        assert(!_.isEmpty(storeName),
                "'storeName' cannot be an empty string.");
        path += _patherize(storeName);

        if(!_.isUndefined(key) && key !== null) {
            assert(!_.isEmpty(key),
                    "'key' cannot be an empty string.");

            path += _patherize(key);
        }
    }

    if(opts.blockId || opts.delta) {
        var params = {};
        if (opts.blockId)  {
            params.blockid = opts.blockId;
        }
        if (opts.delta) {
            params.delta = 1;
        }

        path += '?' + querystring.stringify(params);
    }

    var getArgs = {
        hostname: validatorHost,
        port: validatorPort,
        path: path,
        headers: {
            'Accept': 'application/json',
        }
    };

    return _get(getArgs)
        .then(_unwrapResponseBody);
} 


/**
 * ValidatorClient
 * @constructor
 * @param {string} validatorHost - the host name of the validator
 * @param {number} validatorPort - the port of the validator
 */
function ValidatorClient(validatorHost, validatorPort) {
    assert(validatorHost, "'validatorHost' must be provided.");
    assert(validatorPort, "'validatorPort' must be provided.");

    this.validatorHost = validatorHost;
    this.validatorPort = validatorPort;
}

/**
 * Returns the list of stores on this validator.
 * @returns {Promise} a Promise for the list of store names
 */
ValidatorClient.prototype.getStores = function(opts) {
    opts = _.isUndefined(opts) || _.isNull(opts) ? {} : opts;
    return _getStoreApi(this.validatorHost, this.validatorPort, null, null, opts);
};

/**
 * Returns the list of keys in the store with the given name.
 * @param {storeName}
 * @return {Promise} a Promise for the list of keys in the store
 */
ValidatorClient.prototype.getStore = function(storeName, opts) {
    opts = _.isUndefined(opts) || _.isNull(opts) ? {} : opts;
    return _getStoreApi(this.validatorHost, this.validatorPort, storeName, null, opts);
};

/**
 * Returns the list of objects in the store with the given name.
 * @param {storeName}
 * @return {Promise} a Promise for the list of objects in the store
 */
ValidatorClient.prototype.getStoreObjects = function(storeName, opts) {
    opts = _.isUndefined(opts) || _.isNull(opts) ? {} : opts;
    return _getStoreApi(this.validatorHost, this.validatorPort, storeName, "*", opts);
};

/**
 * Returns the object by key, from the store with the given name.
 * @param {string} storeName
 * @param {string} key
 * @return {Promise} a Promise for the object, if one is found, or null
 */
ValidatorClient.prototype.getStoreObject = function(storeName, key, opts) {
    assert(key != "*",
            "Key should not be '*'.  Use getStoreObjects to retrieve all objects in the store");
    opts = _.isUndefined(opts) || _.isNull(opts) ? {} : opts;
    return _getStoreApi(this.validatorHost, this.validatorPort, storeName, key, opts);
};

/**
 * Submits a transaction, returning a promise containing the transaction transaction id.
 */
ValidatorClient.prototype.sendTransaction = function(txnFamily, txn) {
    return _sendTransaction(this.validatorHost, this.validatorPort, txnFamily, txn);
};


ValidatorClient.prototype._jsonGet = function(uri) {
    return _get({
        hostname: this.validatorHost,
        port: this.validatorPort,
        path: uri,
        headers: {
            'Accept': 'application/json',
        },
    })
    .then(_unwrapResponseBody);
};

/**
 * Returns the list of block ids.  If the options `count` is provided, it
 * limits the number of block ids returned.  Blocks are return in order of most
 * recent to oldest.
 * @param {object} options
 * @return {Promise} a Promise for the list of block ids.
 */
ValidatorClient.prototype.getBlockList = function(opts) {
    opts = _.isUndefined(opts) || _.isNull(opts) ? {} : opts;

    var uri = '/block';
    if (!_.isUndefined(opts.count)) {
        uri += ('?blockcount=' + opts.count);
    }

    return this._jsonGet(uri);
};

/**
 * Returns an object describing the block with the given id.  Optionally,
 * a single field may be requested by passing in `{field: '<fieldName>'}`.
 * @param {string} blockId
 * @param {object} [opts]
 * @return {Promise} a promise for the block info.
 */
ValidatorClient.prototype.getBlock = function(blockId, opts) {
    assert(blockId, "blockId should not be null or empty.");
    opts = _.isUndefined(opts) || _.isNull(opts) ? {} : opts;

    var uri = '/block/' + blockId;
    if(!_.isUndefined(opts.field)) {
        uri += ("/" + opts.field);
    }

    return this._jsonGet(uri);
};

/**
 * Returns a list of transaction ids that have been applied.
 *
 * @param {object} [opts]
 * @return {Promise} a promise for the list of transaction ids.
 */
ValidatorClient.prototype.getTransactions = function(opts) {
    opts = _.isUndefined(opts) || _.isNull(opts) ? {} : opts;

    var uri = '/transaction';
   if (!_.isUndefined(opts.count)) {
        uri += ('?blockcount=' + opts.count);
    }

    return this._jsonGet(uri);
};

ValidatorClient.prototype.getTransaction = function(txnId, opts) {
    assert(txnId, "txnId should not be null or empty.");
    opts = _.isUndefined(opts) || _.isNull(opts) ? {} : opts;

    var uri = '/transaction/' + txnId;
    if(!_.isUndefined(opts.field)) {
        uri += ("/" + opts.field);
    }

    return this._jsonGet(uri);
};

ValidatorClient.prototype.getStatus = function() {
    return this._jsonGet('/status');
};

module.exports = {
    ValidatorClient: ValidatorClient,
};
