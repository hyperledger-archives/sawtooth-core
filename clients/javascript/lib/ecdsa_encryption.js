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
 * @module sawtooth/ecdsa_encryption
 */
"use strict";

var _ = require('underscore');

var bitcoin = require('bitcoinjs-lib');
var BigInteger = require('bigi');

var I = require('immutable');

var signedObject = require('./signed_object');


module.exports = {
    signUpdate: signUpdate,
    verify: verify,
};


var _secondsSinceEpoch = () => Math.floor(Date.now() / 1000);

var _doSign = (field, signingKey, obj, opts) => {
    field = field || 'Signature';
    var signableObj = signedObject.createSignableObj(obj, opts).remove(field);
    
    var objectInCbor = signedObject.toCBOR(signableObj);

    var keyPair = bitcoin.ECPair.fromWIF(signingKey);

    var signature = bitcoin.message.sign(keyPair, objectInCbor).toString('base64'); 

    return signableObj.set(field, signature);
};

var _signTransaction = _.partial(_doSign, 'Signature');
var _signMessage = _.partial(_doSign, '__SIGNATURE__');

/**
 * Signs the update, and wraps it in a message envelope.
 *
 * @param {string} txnType - the type of the transaction.
 * @param {Object} update - the transaction update
 * @param {string} signingKey - the signing key, in WIF format
 * @param {Object} [opts] - options, which may include which fields must be floats
 *   e.g: { ratios: ["Ratio"] }
 * @returns {Object} the signed transaction
 */
function signUpdate(txnType, update, signingKey, opts) {
    if(_.isUndefined(opts)) {
        opts = {};
    }

    if(_.isUndefined(update.Nonce)) {
        update.Nonce = _secondsSinceEpoch();
    }

    var signedTxn = _signTransaction(signingKey, update, opts);

    var message = {
        Transaction:  signedTxn,
        __TYPE__: txnType,
        __NONCE__: _secondsSinceEpoch()
    };
    var signedMsg = _signMessage(signingKey, message, opts);

    if(opts.output == 'json') {
        return signedObject.toJSON(signedMsg);
    } else if (opts.output == 'cbor') {
        return signedObject.toCBOR(signedMsg);
    }

    return signedObject.toJS(signedMsg);
}

function verify(address, signedMessage, opts) {
    var field = '__SIGNATURE__';
    var signature = signedMessage[field];
    var signableObj = signedObject.createSignableObj(signedMessage, opts).remove(field);
    
    var objectInCbor = signedObject.toCBOR(signableObj);
    return bitcoin.message.verify(address, signature, objectInCbor, bitcoin.networks.bitcoin); 
}
