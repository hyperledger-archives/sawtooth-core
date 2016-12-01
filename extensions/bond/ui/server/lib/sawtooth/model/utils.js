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
"use strict";

var _ = require('underscore');

_.mixin({
    mapKeys: _mapKeys
});

var _mapKeys = (m, f) => _.object(_.map(m, (v, k) => [f(k), v]));
var _jsCase = (s) => s && s.length > 0 ? s.charAt(0).toLowerCase() + s.substring(1) : s;
var _capitalize = (s) =>
    s && s !== 'id' && s.length > 0 ? s.charAt(0).toUpperCase() + s.substring(1) : s;

var _fromPersistable = (obj) =>
    obj ?

    _.chain(obj)
     .map((v, k) => [_jsCase(k), v])
     .filter(v => v[1])
     .object()
     .value() :

     obj;

var _toPersistable = (obj) => obj ? _mapKeys(obj, _capitalize) : obj;

// TODO: This might move to ./utils
var _map = (f) => (cursorOrArray) => {
    if(_.isArray(cursorOrArray)) {
        return _.map(cursorOrArray, f);
    } else {
        var cursor = cursorOrArray;
        return {
            next: () => cursor.next().then(f),
            each: (handler, onFinished) => cursor.each(handler, onFinished),
            toArray: () => cursor.toArray().then(array => _.map(array, f)),
        };
    }
};

var _mapCursor = _map;

var _asArray = (asArray) => (query) => asArray ? query.coerceTo('array') : query;
var _cursorToArray = (asArray) => (cursor) => asArray && cursor.toArray ? cursor.toArray() : cursor;

var _findWithOpts = (query, opts) => (collection) => {
    opts = !_.isUndefined(opts) ? opts : {};

    var finder = collection.filter(query);
    if (opts.limit && opts.page && opts.page > 0) {
        finder = finder.skip(opts.limit * opts.page);
    }

    if (opts.limit) {
        finder = finder.limit(opts.limit);
    }
    return finder;
};

var _arrayOrValueParam = (vOrA) =>
    _.isArray(vOrA) ? vOrA : [vOrA];

var _arrayToObject = (a) => 
    _.reduce(a, (memo, v) => {
        memo[v] = true;
        return memo;
    }, {});

var _projectionObject = (fields, fieldGuard) => {
    fieldGuard = fieldGuard || _.identity;
    return _.compose(fieldGuard, _arrayToObject, _arrayOrValueParam)(fields);
};

module.exports = {
    toPersistable: _toPersistable,
    fromPersistable: _fromPersistable,
    mapKeys: _mapKeys,
    mapCursor: _mapCursor,
    cursorToArray: _cursorToArray,
    asArray: _asArray,
    findWithOpts: _findWithOpts,
    projectionObject: _projectionObject,
};
