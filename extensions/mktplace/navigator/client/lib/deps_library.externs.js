/**
 * Copyright 2016 Intel Corporation
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * No license under any patent, copyright, trade secret or other intellectual
 * property right is granted to or conferred upon you by disclosure or delivery
 * of the Materials, either expressly, by implication, inducement, estoppel or
 * otherwise. Any license under such intellectual property rights must be
 * express and approved by Intel(R) in writing.
 */
/**
* Module constructor
*
* @constructor
* @param {number|Fraction} a
* @param {number=} b
*/
var Fraction = function (a, b) { };
Fraction.prototype.n = 0;
Fraction.prototype.d = 1;

var socket = {};
/**
 * @constructor
 * @param {string} url
 */
socket.io = function (url) {};
socket.io.prototype.on = function(evt, cb) {};
socket.io.prototype.disconnect = function () {};

/**
 * @constructor
 * @param {number} n
 */
var Ratio = function(n) {};
Ratio.prototype.encodeCBOR = function(encoder) {};


var bitcoin = {};
bitcoin.hash = function(obj) {};
bitcoin.addressFromPublicKey = function(publicKey) {};
bitcoin.publicKeyHex = function(keyPair) {};
bitcoin.hexToBase64 = function(str) {};

var Clipboard = function(selector) {};
