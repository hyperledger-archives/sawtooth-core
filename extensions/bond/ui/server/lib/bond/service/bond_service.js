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

const r = require('rethinkdb');
const _ = require('underscore');

const block = require('../../sawtooth/model/block');
const connector = require('../../sawtooth/model/db_connector');
const {pagingQuery, pagingResult, pendingTransactions, first} = require('./service_utils');
const {quotesForBondQuery} = require('./quote_queries');
const {toFrac} = require('../../sawtooth/utils');

const _getBondName = (issuer, coup, mat) => {
  var parts = [
    issuer,
    toFrac(coup),
    mat.slice(0, -4) + mat.slice(-2),
    issuer === 'T' ? 'Govt' : 'Corp'
  ];

  return  parts.join(' ');
}

let _pendingTxnXform = (txn, update) => ({
    id: update('ObjectId'),
    'object-id': update('ObjectId'),
    'update-id': txn('id'),
    'pending': true,
    'isin': update('Isin'),
    'cusip': update('Cusip'),
    'issuer': update('Issuer'),
    'corporate-dept-ratings': update('CorporateDebtRatings'),
    'maturity-date': update('MaturityDate'),
    'face-value': update('FaceValue'),
    'amount-outstanding': update('AmountOutstanding'),
    'first-coupon-date': update('FirstCouponDate'),
    'first-settlement-date': null,
    'coupon-type': update('CouponType'),
    'coupon-rate': update('CouponRate'),
    'coupon-frequency': update('CouponFrequency'),
});

let _filterBlockForBonds = (participantId, optionalSearch, currentBlock, db) => {
    let query = pendingTransactions(db, participantId, 'CreateBond', _pendingTxnXform)
                     .union(currentBlock.filter({'object-type': 'bond'}));

    if(!(_.isUndefined(optionalSearch) || _.isEmpty(optionalSearch))) {
        query = query.filter(r.or(r.row('isin').eq(optionalSearch),
                             r.row('cusip').eq(optionalSearch),
                             r.row('issuer').eq(optionalSearch)));
    }
    return query;
};

let _best = (currentBlock, bond, sort) =>
    first(quotesForBondQuery(bond, currentBlock)
      .orderBy(sort)
      .without('object-id', 'isin', 'cusip', 'object-type'));

let _mergeBestQuote = (currentBlock) => (bond) => ({
    'best-bid': _best(currentBlock, bond, r.desc('bid-price')),
    'best-ask': _best(currentBlock, bond, r.asc('ask-price')),
});

let _fetchBlockBonds = (participantId, optionalSearch, opts) => (currentBlock, db) =>
    pagingQuery(_filterBlockForBonds(participantId, optionalSearch, currentBlock, db)
                        .merge(_mergeBestQuote(currentBlock)),
                opts);

let _countBlockBonds = (participantId, optionalSearch) => (currentBlock, db) =>
    _filterBlockForBonds(participantId, optionalSearch, currentBlock, db).count();


let _query = (f, asArray = false) => block.current().advancedQuery(f, asArray);

let _fetchBonds = (participantId, optionalSearch, opts = {}) =>
    Promise.all([_query(_fetchBlockBonds(participantId, optionalSearch, opts), true),
                 _query(_countBlockBonds(participantId, optionalSearch))])
           .then(([data, count]) => pagingResult({ count, data }, opts));

let _fetchBondByIsinOrCusip = (isinOrCusip) =>
    block.current().advancedQuery(currentBlock => {
        let _issuer = (bond) =>
            first(
                currentBlock.filter((obj) =>
                        r.and(obj('object-type').eq('organization'),
                              obj('ticker').eq(bond('issuer'))))
                        .without('object-id','object-type', 'authorization', 'holdings'));

        let _is = (field, value) => r.row.hasFields(field).and(r.row(field).eq(value));

        return first(currentBlock.filter(r.and(r.row('object-type').eq('bond'),
                                                r.or(_is('isin', isinOrCusip),
                                                     _is('cusip', isinOrCusip))))
                                  .merge(bond => ({
                                      'issuing-firm': _issuer(bond),
                                  }))
                                  .merge(_mergeBestQuote(currentBlock)));
    });

let _fetchBondIdentifiers = () =>
    block.current().advancedQuery((block) =>
      block.filter(r.row('object-type').eq('bond')), true)
      .then(results => {
        return results.map(bond =>
          _.chain(bond)
           .pick('id', 'isin', 'cusip')
           .extend({
             name: _getBondName(bond.issuer, bond['coupon-rate'], bond['maturity-date'])
           })
           .value())
      });

module.exports = {
    bonds: _fetchBonds,
    bondByBondIdentifier: _fetchBondByIsinOrCusip,
    bondIdentifiers: _fetchBondIdentifiers,
};
