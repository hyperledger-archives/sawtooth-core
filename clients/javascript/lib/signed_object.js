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

var I = require('immutable');
var cbor = require('cbor');
var streamBuffers = require('stream-buffers');
var sha256 = require('sha256');
var binstring = require('binstring');

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
var _cloneData = function(obj) {
    // This doesn't seem like the fastest way to do this, but it is
    // the most accurate
    return JSON.parse(JSON.stringify(obj));
};

var _convertRatios = function(ratioKeys) {
    var f = function(v, k) {
        if(I.Iterable.isIterable(v)) {
            return v.map(f);
        } else if (ratioKeys.includes(k)) {
            return new Ratio(v);
        }
        return v;
    };
    return f;
};

var _removeRatios = function(v, k) {
    if(I.Iterable.isIterable(v)) {
        return v.map(_removeRatios);
    } else if (v instanceof Ratio) {
        return v.n;
    }
    return v;
};

var _byKey = function(v, k) {
    return k;
};

var _toOrdered = function(k, v) {
    return I.Iterable.isIndexed(v) ? v.toList() : v.toOrderedMap().sortBy(_byKey);
};

var _createSignableObj = function(obj, opts) {
    opts = opts || {};
    return I.fromJS(_cloneData(obj), _toOrdered)
            .map(_convertRatios(I.List(opts.ratios || [])));
};

var _toJS = function(signableObj) {
    return signableObj.map(_removeRatios)
                      .sortBy(_byKey)
                      .toJSON();
};

var _toCBOR = function(signableObj) {
    var encoder = new cbor.Encoder();
    var output = new streamBuffers.WritableStreamBuffer({
        initalSize: (16 * 1024),
    });
    encoder.pipe(output);

    encoder.write(signableObj.sortBy(_byKey).toJSON());

    encoder.end();
    return output.getContents();
};

// Generate a hash string usable as an Object Id
var _generateHash = function(jsObj) {
    var signable = _createSignableObj(jsObj);
    var cbor = _toCBOR(signable);
    var sha = sha256(cbor, {asBytes: true});
    return binstring(sha, {out: 'hex'}).toString();
};

module.exports = {
    createSignableObj: _createSignableObj,
    toJS: _toJS,
    toJSON: function(obj) {
        return JSON.stringify(_toJS(obj));
    },
    toCBOR: _toCBOR,
    Ratio: Ratio,
    generateHash: _generateHash
};
