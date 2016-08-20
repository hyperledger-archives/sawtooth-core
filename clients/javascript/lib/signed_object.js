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

var _convertRatios = (ratioKeys) => {
    let f = (v, k) => {
        if(I.Iterable.isIterable(v)) {
            return v.map(f);
        } else if (ratioKeys.includes(k)) {
            return new Ratio(v);
        }
        return v;
    };
    return f;
};

var _removeRatios = (v, k) => {
    if(I.Iterable.isIterable(v)) {
        return v.map(_removeRatios);
    } else if (v instanceof Ratio) {
        return v.n;
    }
    return v;
};

var _byKey = (v, k) => k;

var _toOrdered = (k, v) => I.Iterable.isIndexed(v) ? v.toList() : v.toOrderedMap().sortBy(_byKey);

var _createSignableObj = (obj, opts) => { 
    opts = opts || {};
   return I.fromJS(_cloneData(obj), _toOrdered)
            .map(_convertRatios(I.List(opts.ratios || [])));
};

var _toJS = (signableObj) =>
    signableObj.map(_removeRatios)
               .sortBy(_byKey)
               .toJS();

module.exports = {
    createSignableObj: _createSignableObj,
    toJS: _toJS,
    Ratio,
};
