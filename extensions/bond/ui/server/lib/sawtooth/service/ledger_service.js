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

var block = require('../model/block');
var transaction = require('../model/transaction');
const {ValidatorClient, SignedObject} = require('sawtooth-client');

var logger = require('../logger').getRESTLogger();
var utils = require('../utils');


const ledgerHost = process.env.LEDGER_HOST || "localhost";
const ledgerPort = parseInt(process.env.LEDGER_PORT || 8800);

const validatorClient = new ValidatorClient(ledgerHost, ledgerPort);

let _floatFields = [];

const _setFloatFields = (fields) =>
    _floatFields = fields;


const _storeTransaction = (transactionId, rawTransaction) =>
    block.current().info()
        .then(info => _.extend({
                            id: transactionId,
                            blockid: info.blockid,
                            InBlock: "PENDING"
                        }, rawTransaction))
        .then(annotatedTransaction => transaction.insert(annotatedTransaction))
        .then(() => transactionId);

const _sendMessage = (txn) => {
    let cborTxn = SignedObject.toCBOR(SignedObject.createSignableObj(txn, {
        ratios: _floatFields,
    }));
    return validatorClient.sendTransaction(txn.__TYPE__, cborTxn);
};

const _createTransaction = (txn, annotations) => {
    annotations = _.isUndefined(annotations) ? {} : annotations;
    return _sendMessage(txn)
        .then(txnId => _storeTransaction(txnId, _.assign(txn.Transaction, annotations)))
        .catch((e) => {
            logger.error('Unable to create transaction', e);
            throw (e);
        });
};

module.exports = {
    setFloatFields: _setFloatFields,

    storeTransaction: _storeTransaction,

    createTransaction: _createTransaction,

    all: (opts) => {
        return Promise.all([transaction.all(_.assign({asArray: true}, opts)),
                            transaction.count({})])
            .then(([txns, count]) => {
                let result = { count, data: txns};

                if (!_.isUndefined(opts.page) && !_.isUndefined(opts.limit)) {
                    var nextPage = opts.page + 1;
                    if (nextPage * opts.limit <= result.count) {
                        result.nextPage = nextPage;
                        result.hasMore = true;
                    } else {
                        result.hasMore = false;
                    }
                }

                return result;
            });
    },

    get: (id) => id ?  transaction.get(id) : Promise.resolve(null),
};
