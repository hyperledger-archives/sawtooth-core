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

var r = require("rethinkdb");

var helpers = require('../../support/helpers');
var block = require('../../../lib/sawtooth/model/block');

describe('Block', () => {

    beforeAll((done) => {
        helpers.createBlock('12345678', [
                {
                    "id" : "0006574c4ae95e17",
                    "account" : "b5a7bbd3460e2b26",
                    "asset" : "d0f4a62634ffba15",
                    "count" : 100,
                    "creator" : "f28412a164abbd4c",
                    "description" : "",
                    "name" : "/holding/teamstock/south15",
                    "object-type" : "Holding",
                    "fqname" : "//participant124/holding/teamstock/south15"
                },
                {
                    "id" : "0002f0c7388f0520",
                    "account" : "a4671b7be3ce0d89",
                    "asset" : "3d643c2f9a756014",
                    "count" : 100,
                    "creator" : "5784cedd2846a619",
                    "description" : "",
                    "name" : "/holding/teamstock/south2",
                    "object-type" : "Holding",
                    "fqname" : "//participant62/holding/teamstock/south2"
                },
                {
                    "id" : "000ae9475a2f920b",
                    "account" : "569501fe511382aa",
                    "asset" : "dcfab85caf48fe99",
                    "count" : 100,
                    "creator" : "61b4746fd90b7cb2",
                    "description" : "",
                    "name" : "/holding/teamstock/east4",
                    "object-type" : "Holding",
                    "fqname" : "//participant100/holding/teamstock/east4"
                },
                {
                    "id" : "000ca6ff9210a8b7",
                    "account" : "858b0e53e01bc52d",
                    "asset" : "35db73367f774652",
                    "count" : 100,
                    "creator" : "0ac17ef9c18e9fdc",
                    "description" : "",
                    "name" : "/holding/teamstock/midwest1",
                    "object-type" : "Holding",
                    "fqname" : "//participant158/holding/teamstock/midwest1"
                },
                {
                    "id":  "000fe708344b8aa0" ,
                    "creator":  "75b625853e62f556" ,
                    "description":  "" ,
                    "name":  "/account/Alice" ,
                    "object-type":  "Account"
                }
                
            ])
            .then(done)
            .catch(helpers.failAsync(done));
    });

    afterAll((done) => {
        helpers.cleanBlock('12345678')
            .then(done)
            .catch(helpers.failAsync(done));
    });

    it('should get the info for the current block', (done) => {
        block.current().info()
            .then(info => {
                expect(info).not.toBeUndefined();
                expect(info.blockid).toBe('12345678');
                expect(info.blocknum).toEqual(jasmine.any(Number));
            })
            .then(done)
            .catch(helpers.failAsync(done));
    });

    describe('count', () => {
        it('should get the current block size', (done) => {
            block.current().count()
                .then(n => expect(n).toBe(5))
                .then(done)
                .catch(helpers.failAsync(done));
        });

        it('should respect filters', (done) => {
            block.current().count({'object-type': 'Holding'})
                .then(n => expect(n).toBe(4))
                .then(done)
                .catch(helpers.failAsync(done));
        });

    });

    it('should get assets by the current block', (done) => {
        block.current().entry('000ca6ff9210a8b7')
            .then(holding => {
                expect(holding).toEqual({
                    "id" : "000ca6ff9210a8b7",
                    "account" : "858b0e53e01bc52d",
                    "asset" : "35db73367f774652",
                    "count" : 100,
                    "creator" : "0ac17ef9c18e9fdc",
                    "description" : "",
                    "name" : "/holding/teamstock/midwest1",
                    "object-type" : "Holding",
                    "fqname" : "//participant158/holding/teamstock/midwest1"
                });
            })
            .then(done)
            .catch(helpers.failAsync(done));
    });

    it('should return null, if entry not found', (done) => {
        block.current().entry('some_unknown_entry')
            .then(entry => {
                expect(entry).toBe(null);
            })
            .then(done)
            .catch(helpers.failAsync(done));
    });

    it('should get all entries in a collections of ids', (done) => {
        block.current().entries(['000fe708344b8aa0', '0006574c4ae95e17'], true)
            .then(entries => {
                expect(entries.length).toBe(2);
                expect(entries).toEqual(jasmine.arrayContaining([
                    {
                        "id":  "000fe708344b8aa0" ,
                        "creator":  "75b625853e62f556" ,
                        "description":  "" ,
                        "name":  "/account/Alice" ,
                        "object-type":  "Account"
                    },
                    {
                        "id" : "0006574c4ae95e17",
                        "account" : "b5a7bbd3460e2b26",
                        "asset" : "d0f4a62634ffba15",
                        "count" : 100,
                        "creator" : "f28412a164abbd4c",
                        "description" : "",
                        "name" : "/holding/teamstock/south15",
                        "object-type" : "Holding",
                        "fqname" : "//participant124/holding/teamstock/south15"
                    }
                ]));
            })
            .then(done)
            .catch(helpers.failAsync(done));
    });

    it('should return an empty array if no ids are found', (done) => {
        block.current().entries(['some_unknown_entry'], true)
            .then(entry => {
                expect(entry).toEqual([]);
            })
            .then(done)
            .catch(helpers.failAsync(done));
    });

    it('should find first by any property', (done) => {
        block.current().findFirst({creator: 'f28412a164abbd4c',
                                   name: '/holding/teamstock/south15'})
            .then(entry => {
                expect(entry).toEqual({
                    "id" : "0006574c4ae95e17",
                    "account" : "b5a7bbd3460e2b26",
                    "asset" : "d0f4a62634ffba15",
                    "count" : 100,
                    "creator" : "f28412a164abbd4c",
                    "description" : "",
                    "name" : "/holding/teamstock/south15",
                    "object-type" : "Holding",
                    "fqname" : "//participant124/holding/teamstock/south15"
                });
            })
            .then(done)
            .catch(helpers.failAsync(done));
    });

    it('should return undefined if nothing is found', (done) => {
        block.current().findFirst({creator: '123456789abcdef'})
            .then(entry => {
                expect(entry).toBeUndefined();
            })
            .then(done)
            .catch(helpers.failAsync(done));
    });

    describe('findExact', () => {

        it('should return an array of matching entries', (done) => {
            block.current().findExact(r.row('name').match('/holding/teamstock/south.*'), {asArray: true})
                .then(entries => {
                    expect(entries.length).toBe(2);
                    expect(entries).toEqual(jasmine.arrayContaining([
                        {
                            "id" : "0006574c4ae95e17",
                            "account" : "b5a7bbd3460e2b26",
                            "asset" : "d0f4a62634ffba15",
                            "count" : 100,
                            "creator" : "f28412a164abbd4c",
                            "description" : "",
                            "name" : "/holding/teamstock/south15",
                            "object-type" : "Holding",
                            "fqname" : "//participant124/holding/teamstock/south15"
                        },
                        {
                            "id" : "0002f0c7388f0520",
                            "account" : "a4671b7be3ce0d89",
                            "asset" : "3d643c2f9a756014",
                            "count" : 100,
                            "creator" : "5784cedd2846a619",
                            "description" : "",
                            "name" : "/holding/teamstock/south2",
                            "object-type" : "Holding",
                            "fqname" : "//participant62/holding/teamstock/south2"
                        },
                    ]));
                })
                .then(done)
                .catch(helpers.failAsync(done));
        });

        it('should allow limits of results', (done) => {
            block.current().findExact(r.row('name').match('/holding/teamstock/south.*'),
                                      {asArray: true, limit: 1})
                .then(entries => {
                    expect(entries.length).toBe(1);
                    expect(entries).toEqual(jasmine.arrayContaining([
                        {
                            "id" : "0002f0c7388f0520",
                            "account" : "a4671b7be3ce0d89",
                            "asset" : "3d643c2f9a756014",
                            "count" : 100,
                            "creator" : "5784cedd2846a619",
                            "description" : "",
                            "name" : "/holding/teamstock/south2",
                            "object-type" : "Holding",
                            "fqname" : "//participant62/holding/teamstock/south2"
                        },
                    ]));
                })
                .then(done)
                .catch(helpers.failAsync(done));
        });

        it('should return an empty array when none are found', (done) => {
            block.current().findExact({name: 'foobar'}, {asArray: true})
                .then(entries => {
                    expect(entries.length).toBe(0);
                })
                .then(done)
                .catch(helpers.failAsync(done));
        });
    });

});
