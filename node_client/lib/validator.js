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
var _ = require('underscore');

function _httpRequest(options, data) {
    return new Promise(function (resolve, reject) {
        var req = http.request(options, function(response) {
            var str = '';
            response.on('data', function(chunk) {
                str += chunk;
            });
            response.on('end', function() {
                resolve({
                    body: str,
                    headers: response.headers,
                    statusCode: response.statusCode,
                });
            });
        });

        req.on('error', reject);

        if(data) {
            req.write(data);
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

function _parseJSONResponse(result) {
    if(result.statusCode === 200) {
        return JSON.parse(result.body);
    }

    // Check for 400, which is the validator's current
    // repsonse for not found, but this may be corrected
    // in the future.
    if(result.statusCode === 400 ||
            result.statusCode === 404) {
        return null;
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

    var postArgs = {
        hostname: validatorHost,
        port: validatorPort,
        path: txnFamily,
        headers: {
            'Content-Type': Buffer.isBuffer(txn) ?
                'application/cbor' :
                'application/json',
            'Content-Length': txn.length
        }
    };

    return _post(postArgs, txn)
        .then(function(result) {
            if(result.statusCode !== 200) {
                throw new Error("Invalid Request: " + result.statusCode);
            }
            return result;
        })
        .then(_parseJSONResponse);
}

function _patherize(s) {
    return s[0] == '/' ? s : ('/' + s);
}

function _getStoreApi(validatorHost, validatorPort, storeName, key) {
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
    var getArgs = {
        hostname: validatorHost,
        port: validatorPort,
        path: path,
        headers: {
            'Accept': 'application/json',
        }
    };

    return _get(getArgs)
        .then(_parseJSONResponse);
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
ValidatorClient.prototype.getStores = function() {
    return _getStoreApi(this.validatorHost, this.validatorPort);
};

/**
 * Returns the list of keys in the store with the given name.
 * @param {storeName}
 * @return {Promise} a Promise for the list of keys in the store
 */
ValidatorClient.prototype.getStore = function(storeName) {
    return _getStoreApi(this.validatorHost, this.validatorPort, storeName);
};

/**
 * Returns the list of objects in the store with the given name.
 * @param {storeName}
 * @return {Promise} a Promise for the list of objects in the store
 */
ValidatorClient.prototype.getStoreObjects = function(storeName) {
    return _getStoreApi(this.validatorHost, this.validatorPort, storeName, "*");
};

/**
 * Returns the object by key, from the store with the given name.
 * @param {string} storeName
 * @param {string} key
 * @return {Promise} a Proimse for the object, if one is found, or null
 */
ValidatorClient.prototype.getStoreObject = function(storeName, key) {
    assert(key != "*",
            "Key should not be '*'.  Use getStoreObjects to retrieve all objects in the store");
    return _getStoreApi(this.validatorHost, this.validatorPort, storeName, key);
};

ValidatorClient.prototype.sendTransaction = function(txnFamily, txn) {
    return _sendTransaction(this.validatorHost, this.validatorPort, txnFamily, txn);
};

module.exports = {
    sendTransaction: _sendTransaction,
    getStores: function(validatorHost, validatorPort) {
        return _getStoreApi(validatorHost, validatorPort);
    },
    getStore: function(validatorHost, validatorPort, storeName) {
        return _getStoreApi(validatorHost, validatorPort, storeName);
    },
    getStoreObjects: function(validatorHost, validatorPort, storeName) {
        return _getStoreApi(validatorHost, validatorPort, storeName, "*");
    },
    getStoreObject: function(validatorHost, validatorPort, storeName, key) {
        assert(key != "*",
                "Key should not be '*'.  Use getStoreObjects to retrieve all objects in the store");
        return _getStoreApi(validatorHost, validatorPort, storeName, key);
    },

    ValidatorClient: ValidatorClient,
};
