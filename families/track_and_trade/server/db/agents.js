/**
 * Copyright 2017 Intel Corporation
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
 * ----------------------------------------------------------------------------
 */
'use strict'

const r = require('rethinkdb')

const db = require('./')

const hasCurrentBlock = currentBlock => obj => {
  return r.and(
    obj('startBlockNum').le(currentBlock),
    obj('endBlockNum').gt(currentBlock)
  )
}

const getAttribute = attr => obj => obj(attr)
const getRecordId = getAttribute('recordId')
const getPublicKey = getAttribute('publicKey')
const getName = getAttribute('name')
const getReporters = getAttribute('reporters')
const getAuthorized = getAttribute('authorized')

const hasPublicKey = key => obj => {
  return r.eq(
    key,
    getPublicKey(obj)
  )
}

const getAssociatedAgentId = role => record => record(role).nth(-1)('agentId')
const getOwnerId = getAssociatedAgentId('owners')
const getCustodianId = getAssociatedAgentId('custodians')

const isAssociatedWithRecord = association => agent => record => {
  return r.eq(
    association(record),
    getPublicKey(agent)
  )
}

const isRecordOwner = isAssociatedWithRecord(getOwnerId)
const isRecordCustodian = isAssociatedWithRecord(getCustodianId)

const isReporter = agent => property => {
  return getReporters(property)
    .filter(hasPublicKey(getPublicKey(agent)))
    .do(seq => r.branch(
      seq.isEmpty(),
      false,
      getAuthorized(seq.nth(0))
    ))
}

const queryWithCurrentBlock = query => {
  return r.table('blocks')
    .orderBy(r.desc('blockNum'))
    .nth(0)('blockNum')
    .do(query)
}

const getTable = (tableName, currentBlock) =>
      r.table(tableName).filter(hasCurrentBlock(currentBlock))

const listQuery = queryWithCurrentBlock(currentBlock => {
  return getTable('agents', currentBlock)
    .map(agent => r.expr({
      'name': getName(agent),
      'key': getPublicKey(agent),
      'owns': getTable('records', currentBlock)
        .filter(isRecordOwner(agent))
        .map(getRecordId)
        .distinct(),
      'custodian': getTable('records', currentBlock)
        .filter(isRecordCustodian(agent))
        .map(getRecordId)
        .distinct(),
      'reports': getTable('properties', currentBlock)
        .filter(isReporter(agent))
        .map(getRecordId)
        .distinct()
    })).coerceTo('array')
})

const list = () => db.runQuery(listQuery)

module.exports = {
  list
}
