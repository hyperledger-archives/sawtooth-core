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

const MAX_BLOCK = Number.MAX_SAFE_INTEGER

const hasMaxBlock = obj => obj('endBlockNum').eq(MAX_BLOCK)

const getAttribute = attr => obj => obj(attr)
const getRecordId = getAttribute('recordId')
const getPublicKey = getAttribute('publicKey')
const getName = getAttribute('name')

const getAssociatedAgentId = role => record => record(role).nth(-1)('agentId')
const getOwnerId = getAssociatedAgentId('owners')
const getCustodianId = getAssociatedAgentId('custodians')

const isAssociatedWithRecord =
      association => agent => record => r.eq(
        association(record),
        agent('publicKey')
      )

const isRecordOwner = isAssociatedWithRecord(getOwnerId)
const isRecordCustodian = isAssociatedWithRecord(getCustodianId)

const isReporter = agent => property => {
  return property('reporters')
    .map(getPublicKey)
    .contains(getPublicKey(agent))
}

const getAgentsQuery = agents => {
  return agents
    .filter(hasMaxBlock)
    .map(agent => r.expr({
      'name': agent('name'),
      'key': agent('publicKey'),
      'owns': r.table('records')
        .filter(hasMaxBlock)
        .filter(isRecordOwner(agent))
        .map(getRecordId)
        .distinct(),
      'custodian': r.table('records')
        .filter(hasMaxBlock)
        .filter(isRecordCustodian(agent))
        .map(getRecordId)
        .distinct(),
      'reports': r.table('properties')
        .filter(hasMaxBlock)
        .filter(isReporter(agent))
        .map(property => r.expr({
          'recordId': getRecordId(property),
          'property': getName(property)
        }))
        .distinct()
    }))
}

const getAgents = () => db.queryTable('agents', getAgentsQuery)

module.exports = {
  getAgents
}
