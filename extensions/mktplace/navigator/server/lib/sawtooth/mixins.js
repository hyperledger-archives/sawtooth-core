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
 * Sawtooth Mixins
 *
 * In order to used this module, simply call
 *
 * ```
 * require('<relative_path_to>/mixins');
 * ```
 *
 * @module sawtooth/mixins
 */
"use strict";

var _ = require('underscore');

/**
 *
 * Underscore extension for a spread function.
 *
 * Called via `_.spread(...)`
 *
 * @param {Function} f - a function f(...args) => *
 * @returns {Function} a function f(Object[]) => *
 * @example
 * let join = _.spread((a, b) => a + ", " + b);
 *
 * join(["Alice", "Bob"]);
 * // => 'Alice, Bob'
 */
let spread = (f) => (a) => f.apply(null, a);


_.mixin({
    spread
});
