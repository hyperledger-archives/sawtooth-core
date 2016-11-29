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
require('../../sawtooth/mixins');

var r = require('rethinkdb');

var block = require('../../sawtooth/model/block');
var transaction = require('../../sawtooth/model/transaction');
var exchangeService = require('./exchange_service');
var {UpdateTypes} = require('../constants');
var {TransactionStatuses} = require('../../sawtooth/constants');

var logger = require('../../sawtooth/logger').getRESTLogger();

const {mergeAssetSettings} = require('./service_common');



let _mergeParticipant = (block) =>  (p) => ({
    holdings: block.filter({ creator: p('id'), 'object-type': 'Holding' })
                   .merge(mergeAssetSettings(block)).coerceTo('array'),
    accounts: block.filter({ creator: p('id'), 'object-type': 'Account'})
                   .coerceTo('array'),
});

module.exports = {
    getByAddress: (address) => 
        block.current().findFirst({address: address})
            .then(participant => {
                if(participant) {
                    return participant;
                }

                return transaction.findExact(
                        r.and(r.row('Updates').nth(0)('UpdateType').eq(UpdateTypes.REGISTER_PARTICIPANT),
                              r.row('Status').eq(TransactionStatuses.PENDING),
                              r.row('address').eq(address)),
                        {asArray: true})
                    .then(txns => _.map(txns, (t) => ({
                                                id: t.id,
                                                displayName: t.Updates[0].Name,
                                                name: t.Updates[0].Name,
                                                description: t.Updates[0].Description,
                                                pending: true
                                              })))
                    .then(_.first);
            }),

    participant: (id) => 
        block.current().advancedQuery(block =>
                    block.get(id)
                         .do(p =>
                             r.branch(p,
                                      p.merge(_mergeParticipant(block)),
                                      null)))
            .then(party => {
                if (!party) {
                    return undefined;
                }

                var accountsPromise;
                if(_.isEmpty(party.accounts)) {
                    accountsPromise = transaction.findExact(
                        r.and(r.row('Updates').nth(0)('UpdateType').eq(UpdateTypes.REGISTER_ACCOUNT),
                              r.row.hasFields('creator'),
                              r.row('creator').eq(id)),
                        {asArray: true})
                    .then(txns => _.map(txns, t => ({
                        id: t.id,
                        name: t.Updates[0].Name,
                        description: t.Updates[0].Description,
                        pending: true
                    })));
                } else {
                    accountsPromise = Promise.resolve(party.accounts);
                }

                return accountsPromise.then(accounts => {
                    party.account = _.first(accounts);
                    return _.omit(party, 'address', 'accounts');
                });

            }),

    getUsersNameAndIds: () =>
        block.current().projection({'object-type': 'Participant'}, ['name'], true)
};
