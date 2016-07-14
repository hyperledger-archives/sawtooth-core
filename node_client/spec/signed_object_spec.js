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

var chai = require('chai');
var chaiImmutable = require('chai-immutable');
chai.use(chaiImmutable);

var assert = chai.assert;

var {Ratio, createSignableObj, toJS} = require('../lib/signed_object');
var {OrderedMap} = require('immutable');

describe('signed_object', () => {

    describe('#createSignableObj()', () => {

        it('should return an sorted, immutable object', () => {
            var signable = createSignableObj({x: 1, y: 2, a: "hello", b: "goodbye"});

            assert.equal(
                    OrderedMap({
                        a: "hello",
                        b: "goodbye",
                        x: 1,
                        y: 2
                    }),
                    signable);
        });

        it('should return an object with ratios', () => {
            var signable = createSignableObj({x: 1, r: 2}, {ratios: "r"});

            assert.equal(1, signable.get('x'));
            assert.instanceOf(signable.get('r'), Ratio);

        });
    });

    describe('#toJS', () => {

        it ('should return the js from the immutable object', () => {
            var jsObj = toJS(OrderedMap({y: 1, x: 2}));

            assert.deepEqual({x: 2, y: 1}, jsObj);
        });

        it('should remove any ratios', () => {
            var jsObj = toJS(OrderedMap({x: new Ratio(2), y: 4}));
            
            assert.deepEqual({x: 2, y: 4}, jsObj);
        });
    });
});
