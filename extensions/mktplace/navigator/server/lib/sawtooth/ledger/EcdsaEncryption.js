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
/**
 * Sawtooth ledger EcdsaEncryption module
 * @module sawtooth/ledger/EcdsaEncryption
 */
"use strict";

var _ = require('underscore');

var bitcoin = require('bitcoinjs-lib');
var cbor = require('cbor');
var BigInteger = require('bigi');
var ecdsa = require('../../../node_modules/bitcoinjs-lib/src/ecdsa');

var I = require('immutable');

var PythonShell = require('python-shell');

var logger = require('../logger').getRESTLogger();


module.exports = {
    signUpdate: signUpdate,
    verify: verify,
    addressFromSignedMessage: addressFromSignedMessage,
    recoverPublicKey: recoverPublicKey,
};

function Ratio(n) {
    this.n = n;
}

Ratio.prototype.encodeCBOR = function (encoder) {
    encoder._pushFloat(this.n);
};

/**
 * Take any object and clone it's data.
 * E.g. if it's a function instance (i.e. new MyObject()), it will
 * produce a map of just the fields.
 * @private
 */
var _cloneData = (obj) => 
    // This doesn't seem like the fastest way to do this, but it is
    // the most accurate
    JSON.parse(JSON.stringify(obj));

var _convertRatios = (v, k) => {
    if(I.Iterable.isIterable(v)) {
        return v.map(_convertRatios);
    } else if (k === 'Ratio') {
        return new Ratio(v);
    }
    return v;
};

var _removeRatios = (v, k) => {
    if(I.Iterable.isIterable(v)) {
        return v.map(_removeRatios);
    } else if (k === 'Ratio') {
        return v.n;
    }
    return v;
};

var _byKey = (v, k) => k;

var _createSignableObj = (obj) => 
   I.fromJS(obj, (k, v) =>
           I.Iterable.isIndexed(v) ? v.toList() : v.toOrderedMap().sortBy(_byKey))
    .map(_convertRatios);

var transactionType = "/mktplace.transactions.MarketPlace/Transaction";

var _secondsSinceEpoch = () => Math.floor(Date.now() / 1000);

var _doSign = (signingKey, obj, field) => {
    field = field || 'Signature';
    var signableObj = _createSignableObj(_cloneData(obj)).remove(field);
    
    var objectInCbor = cbor.encode(signableObj.toJS());

    var keyPair = bitcoin.ECPair.fromWIF(signingKey);

    var hash = bitcoin.message.magicHash(objectInCbor, bitcoin.networks.bitcoin);

    var signature = keyPair.sign(hash);
    var e = BigInteger.fromBuffer(hash);
    var i = ecdsa.calcPubKeyRecoveryParam(e, signature, keyPair.Q);

    signature = signature.toCompact(i, keyPair.compressed).toString('base64');

    return signableObj.set(field, signature)
                      .map(_removeRatios)
                      .sortBy(_byKey)
                      .toJS();
};

var _signTransaction = _.partial(_doSign, _, _, 'Signature');
var _signMessage = _.partial(_doSign, _, _, '__SIGNATURE__');

/**
 * Signs the update, and wraps it in a message envelope.
 *
 * @param {Object} update
 * @param {string} signingKey
 * @returns {Object} the signed transaction
 */
function signUpdate(update, signingKey) {
    if(_.isUndefined(update.Nonce)) {
        update.Nonce = _secondsSinceEpoch();
    }

    var signedTxn = _signTransaction(signingKey, update);

    var message = {
        Transaction:  signedTxn,
        __TYPE__: transactionType,
        __NONCE__: _secondsSinceEpoch()
    };
    var signedMsg = _signMessage(signingKey, message);

    /*
    console.log('
');
    console.log(signedMsg);
    console.log('
');
    */

    return Promise.resolve(signedMsg);
}

function verify(address, signedMessage) {
    var field = '__SIGNATURE__';
    var signature = signedMessage[field];
    var signableObj = _createSignableObj(_cloneData(signedMessage)).remove(field);
    
    var objectInCbor = cbor.encode(signableObj.toJS());
    return bitcoin.message.verify(address, signature, objectInCbor, bitcoin.networks.bitcoin); 
}

function _recoverKeyPair(signedMessage) {
    var field = '__SIGNATURE__';
    var signature = new Buffer(signedMessage[field], 'base64');
    var signableObj = _createSignableObj(_cloneData(signedMessage)).remove(field);
    var objectInCbor = cbor.encode(signableObj.toJS());

    var hash = bitcoin.message.magicHash(objectInCbor, bitcoin.networks.bitcoin);

    var parsed = bitcoin.ECSignature.parseCompact(signature);
    var e = BigInteger.fromBuffer(hash);
    var Q = ecdsa.recoverPubKey(e, parsed.signature, parsed.i);

    return new bitcoin.ECPair(null, Q, {
        compressed: parsed.compressed,
        network: bitcoin.networks.bitcoin,
    });
}


function addressFromSignedMessage(signedMessage) {
    var keyPair = _recoverKeyPair(signedMessage);

    return keyPair.getAddress();
}

function recoverPublicKey(signedMessage) {
    var keyPair = _recoverKeyPair(signedMessage);
    return keyPair.getPublicKeyBuffer().toString('hex');
}
