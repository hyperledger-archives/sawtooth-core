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
 * @module sawtooth/validation
 */
"use strict";

var promise = require('bluebird');

function SchemaError(message, errObj) {
    message = message || 'SchemaError';
    errObj = errObj || {};

    this.message = message + '\n' + JSON.stringify(errObj, null, 2);
    this.errObj = errObj;

    Error.captureStackTrace(this, SchemaError);
}

SchemaError.prototype = Error.prototype;

module.exports = {
    /**
     * Regex for URLs.
     */
    url: /^(https?:\/\/)?([\da-z\.-]+)\.([a-z\.]{2,6})([\/\w \.-]*)*\/?$/,
    /**
     * Regex for email addresses.
     */
    email: /^(([^<>()\[\]\\.,;:\s@"]+(\.[^<>()\[\]\\.,;:\s@"]+)*)|(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/,

    /**
     * Regex for HEX colors. 
     *
     * E.g. `#CC00FF`
     */
    hexColor: /#([a-f]|[A-F]|[0-9]){3}(([a-f]|[A-F]|[0-9]){3})?\b/,

    /**
     * Error thrown on schema-based validation.
     *
     * @constructor
     */
    SchemaError: SchemaError,

    /**
     * Validates an object with a schema.
     *
     * @param {Function} schema - a [js-schema](https://github.com/molnarg/js-schema) schema function
     * @param {Object} obj - the object to validate
     * @param {string} [msg] - an optional message to add to the error on failure
     *
     * @method
     * @static
     */
    validate: (schema, obj, msg) =>
        promise.attempt(() => {
            if(!schema(obj)) {
                throw new SchemaError(msg || "Validation Failed!",
                                      schema.errors(obj));
            } 
        })
};
