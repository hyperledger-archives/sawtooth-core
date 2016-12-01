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
 * Sawtooth Utils
 *
 * This utils are primarily used for dealing with the ins and outs of ledger signing
 * and submission.
 * @module sawtooth/utils
 */

'use strict';

const sha256 = require('sha256');
const conv = require('binstring');


const _toFrac = (n, denom=8) => {
    if (n < 0) return '-' + _toFrac(-n, denom);

    let numer = Math.round(n * denom);
    const getGcd = (x, y) =>  y ? getGcd(y, x % y) : x;
    const gcd = getGcd(numer, denom);
    numer /= gcd;
    denom /= gcd;

    if (denom === 1) return '' + numer;
    if (numer < denom) return numer + '/' + denom;

    return Math.floor(numer / denom) + ' ' + numer % denom + '/' + denom;
}

module.exports = {
    /**
     * Makes sure the the given string transactions with items labeled as Ratio are
     * always marshelled as a float.
     *
     * For example:
     * ```
     * makeSureRatioIsFloat("{ Ratio: 1 }")
     *
     * => "{ Ratio: 1.0 }"
     * ```
     *
     * This is important for ensuring the objects are unmarshalled correctly by the validator.
     *
     * @param {string} s - the transaction string
     * @returns {string} the new transaction with modifications made as necessary
     */
    makeSureFieldIsFloat: (s, fields) => {
        var transactionsString = s || '';
        var regex = "\"(?:" + fields.join('|')  + ")\":\\d+(?=\\,|\\}|$)";
        var matches = null;
        while((matches = transactionsString.match(regex)) !== null) {
            var newStr = matches[0] + ".0";
            transactionsString = transactionsString.replace(
                   new RegExp(matches[0], 'g'), newStr);
        }
        return transactionsString;
    },

    /**
     * Given a signature, returns an ledger ID
     *
     * @param {string} signature - the signature to convert
     * @returns {string} the transaction id
     */
    getTransactionIDFromSignature: (signature) => {
        var sha = sha256(signature, { asBytes: true });
        var hex = conv(sha,{out : 'hex'});
        return hex.toString().substring(0,16);
    },

    /*
     * Converts a floating point number into a fraction string
     */
    toFrac: _toFrac
};
