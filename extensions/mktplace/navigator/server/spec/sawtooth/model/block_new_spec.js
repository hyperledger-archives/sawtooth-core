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

var helpers = require('../../support/helpers');
var block = require('../../../lib/sawtooth/model/block');

describe('New Block', () => {
    afterAll((done) => done());

    it('should return a default block info', (done) =>
        block.current().info()
            .then(info => {
                expect(info.blockid).toBe('0');
                expect(info.blocknum).toBe(0);
            })
            .then(done)
            .catch(helpers.failAsync(done)));

    it('should return undefined for entry', (done) =>
        block.current().entry('123')
            .then(entry => {
                expect(entry).toBe(null);
            })
            .then(done)
            .catch(helpers.failAsync(done)));

    it('should return an empty array of entries', (done) =>
        block.current().entries(["a", "b", "c"], true)
            .then(entries => {
                expect(entries).toEqual([]);
            })
            .then(done)
            .catch(helpers.failAsync(done)));


    it('should return undefined for findFirst', (done) =>
        block.current().findFirst({_id: '123'})
            .then(entry => {
                expect(entry).toBeUndefined();
            })
            .then(done)
            .catch(helpers.failAsync(done)));

    it('should return empty for findExact', (done) =>
        block.current().findExact({'object-type': 'Participant'}, {asArray: true})
            .then(entries => {
                expect(entries).toEqual([]);
            })
            .then(done)
            .catch(helpers.failAsync(done)));
});
