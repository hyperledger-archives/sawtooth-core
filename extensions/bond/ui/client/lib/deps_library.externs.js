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

/* jshint unused:vars */
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
bitcoin.hexToBase64 = function(str) {};
bitcoin.publicKeyHex = function(keyPair) {};
bitcoin.sign = function(keyPair, msg) {};

/**
 * ECPair constructor
 * @constructor
 * @param d
 * @param Q
 * @param opts
 */
bitcoin.ECPair = function(d, Q, opts) {};
bitcoin.ECPair.makeRandom = function() {};
bitcoin.ECPair.fromWIF = function(wifStr) {};
bitcoin.ECPair.prototype.toWIF = function() {};
bitcoin.ECPair.prototype.getAddress = function() {};

var Clipboard = function(selector) {};
