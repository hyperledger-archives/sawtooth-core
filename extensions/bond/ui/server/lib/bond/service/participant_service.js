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
var org = require('./organization_service');

const {TransactionStatuses} = require('../../sawtooth/constants');
const ROLE_NOT_FOUND = 'UNKNOWN ROLE';

const _fetchParticipantByAddress = address =>
  block.current().findFirst({'object-type': 'participant',
                             'key-id': address})
  .then(participant => {
    if (participant) {
      return participant;
    }

    return connector.exec(db =>
      db.table('transactions')
        .filter(r.and(r.row('key-id').eq(address),
                      r.row('Status').eq(TransactionStatuses.PENDING)))
        .map(txn => {
          var update = txn('Updates')(0);
          return {
            'object-id': update('ObjectId'),
            'username': update('Username'),
            'firm-id': update('FirmId'),
            'key-id': txn('key-id'),
            'id': update('ObjectId'),
            'pending': true,
          };
        })
        .limit(1)
        .coerceTo('array'))
      .then(_.first);
  });

const _fetchParticipantNamesAndAddresses = params => {
  var queries = _.extend({'object-type': 'participant'},
                         _.pick(params, 'username'));

  var ands = _.map(queries, (val, row) => r.row(row).eq(val));

  return block.current().advancedQuery(block =>
    block.filter(r.and(r.args(ands)))
         .pluck('id', 'username', 'key-id'),
  true);
};

const _fetchParticipantWithFirm = address =>
  _fetchParticipantByAddress(address)
  .then(participant => {
    if (participant) {
      return org.organizationById(participant['firm-id'])
      .then(organization =>
        _.extend(participant,
                {'firm-name': organization.name,
                'firm-role': organization.authorization.reduce((role, auth) => {
                  if (auth['participant-id'] === participant.id) return auth.role;
                  return role;
                }, ROLE_NOT_FOUND)}));
    }
  });

module.exports = {
  participantByAddress: _fetchParticipantByAddress,
  participantNamesAndAddresses: _fetchParticipantNamesAndAddresses,
  participantWithFirm: _fetchParticipantWithFirm
};
