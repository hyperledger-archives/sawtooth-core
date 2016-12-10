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

'use strict';

var r = require('rethinkdb');
var _ = require('underscore');

var block = require('../../sawtooth/model/block');
var connector = require('../../sawtooth/model/db_connector');

const _fetchOrganizations = () =>
  block.current().advancedQuery(
    currentBlock => currentBlock.filter(r.row('object-type').eq('organization'))
                                .without('authorization', 'object-type'),
    true);

const _fetchOrganizationById = (id) =>
  block.current().advancedQuery(
    currentBlock => currentBlock.filter(r.and(r.row('object-type').eq('organization'),
                                              r.row('id').eq(id)))
                                .without('object-type', 'ref-count', 'object-id')
                                .limit(1)
                                .coerceTo('array')
                                .do((res) => r.branch(res.isEmpty(), null, res.nth(0))));

module.exports = {
    organizations: _fetchOrganizations,
    organizationById: _fetchOrganizationById
};
