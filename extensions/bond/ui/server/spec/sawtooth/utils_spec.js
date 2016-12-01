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

let utils = require('../../lib/sawtooth/utils');

describe('utils', () => {
    describe("makeSureFieldIsFloat()", () => {

        it('should ensure float in json', () => {
            let o = {x: 1};
            expect(utils.makeSureFieldIsFloat(JSON.stringify(o), ["x"]))
                .toBe("{\"x\":1.0}");
        });

        it('should ignore fields that are already floats', () => {
            let o = {x: 1.2};
            expect(utils.makeSureFieldIsFloat(JSON.stringify(o), ["x"]))
                .toBe("{\"x\":1.2}");
        });

        it('should ensure multiple fields are floats', () => {
            let o = {
                x: 1,
                y: 2,
                foo: 3
            };
            expect(utils.makeSureFieldIsFloat(JSON.stringify(o), ["x", "foo"]))
                .toBe("{\"x\":1.0,\"y\":2,\"foo\":3.0}");
        });

        it('should ensure multiple fields of the same name are floats,', () => {
            let o = {
                a: {
                    x: 1,
                },
                b: {
                    x: 1,
                },
                c: {
                    x: 1,
                }
            };

            expect(utils.makeSureFieldIsFloat(JSON.stringify(o), ["x", "foo"]))
                .toBe("{\"a\":{\"x\":1.0},\"b\":{\"x\":1.0},\"c\":{\"x\":1.0}}");
        });
    });
});
