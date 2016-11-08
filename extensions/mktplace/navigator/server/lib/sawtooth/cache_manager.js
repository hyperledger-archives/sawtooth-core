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
 * Sawtooth Cache Manager
 *
 * Manages function result cacheing (essentially memoization), and allows all
 * the caches to be cleared at once.
 *
 * @module sawtooth/cache_manager
 *
 * @example
 *
 * const cacheManager = require('<relative_path>/sawtooth/cache_manager');
 */
"use strict";

const _ = require('underscore');
const {List: IList} = require('immutable');

let _caches = IList();

module.exports = {

    /**
     * Create a cached function. The given function will return a cached
     * result for the same parameters i.e. memoized.
     * @param {Function} f - `f(...any) => any
     * @returns {Function} the memoized function
     */
    cacheFn: (f) => {
        let memoized = _.memoize(f);
        _caches = _caches.push(memoized);
        return memoized;
    },

    /**
     * Clears all caches for the managed, memoized functions.
     */
    clearCaches: () => {
        _caches.forEach(f => f.cache = {});
    },

};
