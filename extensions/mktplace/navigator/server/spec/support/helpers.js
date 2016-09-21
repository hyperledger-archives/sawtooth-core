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
var r = require('rethinkdb');
var connector = require('../../lib/sawtooth/model/db_connector');


var _cleanBlock = (blockId) =>
    connector.exec((db) => db.table('chain_info').delete())
             .then(connector.thenExec(db => db.tableDrop('blk' + blockId)));


module.exports = {
    failAsync: (done) => (e) => {
        if(e) {
            done.fail(e);
        } else {
            done.fail("Unknown asyncronous failure");
        }
    },

    createBlock: (blockId, entries) => 
        connector.exec((db) =>
                db.table('chain_info').insert({
                    id: 'currentblock',
                    blockid: blockId, 
                    blocknum: Date.now()
                }, { conflict: "replace" }))
            .then(connector.thenExec(db => db.tableCreate('blk' + blockId)))
            .then(() =>
                    !_.isEmpty(entries) ?
                    connector.exec(db => db.table('blk' + blockId).insert(entries)) :
                    null),

    cleanBlock: _cleanBlock,
    
    thenCleanBlock: (blockId) => () => _cleanBlock(blockId),
    
    generateExchanges: (n, status) =>
        _.chain(_.range(n))
         .map(x => ({
                id: ''  + (10000 + x),
                Status: status,
                created: Date.now(),

                // Original transaction fields
                TransactionType: '/MarketPlaceTransaction',
                Signature: 'some_long_signature_string',
                Nonce: Date.now(),
                Update: {
                    UpdateType: "/mktplace.transactions.ExchangeUpdate/Exchange",
                    OfferIDList: ['some_offer_id'],
                },
         }))
         .value(),

};
