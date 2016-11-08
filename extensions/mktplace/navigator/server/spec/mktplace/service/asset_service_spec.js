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

var helpers = require('../../support/helpers');
var assetService = require('../../../lib/mktplace/service/asset_service');

describe('AssetService', () => {
    beforeAll((done) => {
        helpers.createBlock('45678', [
                    {
                        "id" : "d235fa3207d73f17",
                        "asset-type" : "70afa6a11ed3bb45",
                        "consumable" : true,
                        "creator" : "4f2ede53e0e08e6f",
                        "description" : "",
                        "divisible" : false,
                        "name" : "/asset/currency/mikel",
                        "object-type" : "Asset",
                        "restricted" : true,
                        "fqname" : "//immxleague/asset/currency/mikel"
                    },
                    {
                        "id" : "847f47d2b47fc8dc",
                        "asset-type" : "50d3dc7b9bed498c",
                        "consumable" : true,
                        "creator" : "4f2ede53e0e08e6f",
                        "description" : "",
                        "divisible" : false,
                        "name" : "/asset/team/east1",
                        "object-type" : "Asset",
                        "restricted" : true,
                        "fqname" : "//immxleague/asset/team/east1"
                    },
                    {
                        "id" : "4ab87b6c86d5ed91",
                        "asset-type" : "50d3dc7b9bed498c",
                        "consumable" : true,
                        "creator" : "4f2ede53e0e08e6f",
                        "description" : "",
                        "divisible" : false,
                        "name" : "/asset/team/east10",
                        "object-type" : "Asset",
                        "restricted" : true,
                        "fqname" : "//immxleague/asset/team/east10"
                    },
                    {
                        "id" : "79138499d714c14b",
                        "asset-type" : "50d3dc7b9bed498c",
                        "consumable" : true,
                        "creator" : "4f2ede53e0e08e6f",
                        "description" : "",
                        "divisible" : false,
                        "name" : "/asset/team/east11",
                        "object-type" : "Asset",
                        "restricted" : true,
                        "fqname" : "//immxleague/asset/team/east11"
                    },
                    {
                        "id" : "3079bdf3c47f231c",
                        "asset-type" : "50d3dc7b9bed498c",
                        "consumable" : true,
                        "creator" : "4f2ede53e0e08e6f",
                        "description" : "",
                        "divisible" : false,
                        "name" : "/asset/company/acme",
                        "object-type" : "Asset",
                        "restricted" : true,
                        "fqname" : "//othernamespace/asset/company/acme"
                    },
                    {
                        "id" : "70afa6a11ed3bb45",
                        "creator" : "4f2ede53e0e08e6f",
                        "description" : "Currency asset type",
                        "name" : "/asset-type/currency",
                        "object-type" : "AssetType",
                        "restricted" : true,
                        "fqname" : "//immxleague/asset-type/currency"
                    },
                    {
                        "id" : "50d3dc7b9bed498c",
                        "creator" : "4f2ede53e0e08e6f",
                        "description" : "Team stock asset type",
                        "name" : "/asset-type/teamstock",
                        "object-type" : "AssetType",
                        "restricted" : true,
                        "fqname" : "//immxleague/asset-type/teamstock"
                    }
        ])
        .then(done)
        .catch(helpers.failAsync(done));
    });

    afterAll((done) => {
        helpers.cleanBlock('45678')
            .then(done)
            .catch(helpers.failAsync(done));
    });

    it('should list all assets', (done) => {
        assetService.assets()
            .then(assets => {
                expect(assets.length).toBe(5);
                expect(_.pluck(assets, 'id')).toEqual(jasmine.arrayContaining([
                    'd235fa3207d73f17',
                    '847f47d2b47fc8dc',
                    '4ab87b6c86d5ed91',
                    '79138499d714c14b',
                    '3079bdf3c47f231c'
                ]));
            })
            .then(done)
            .catch(helpers.failAsync(done));
    });

    it('should list all asset types', (done) => {
        assetService.assetTypes()
            .then(assetTypes => {
                expect(assetTypes.length).toBe(2);
                expect(_.pluck(assetTypes, 'id')).toEqual(jasmine.arrayContaining([
                    '50d3dc7b9bed498c',
                    '70afa6a11ed3bb45',
                ]));
            })
            .then(done)
            .catch(helpers.failAsync(done));
    });

});
