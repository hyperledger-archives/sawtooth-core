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

/* Helpers */

const getAttribute = attr => obj => obj(attr)
const getRecordId = getAttribute('recordId')
const getName = getAttribute('name')
const getPublicKey = getAttribute('publicKey')
const getDataType = getAttribute('dataType')
const getReporters = getAttribute('reporters')
const getAuthorization = getAttribute('authorized')
const getReportedValues = getAttribute('reportedValues')

const getAssociatedAgentId = role => record => record(role).nth(-1)('agentId')
const getOwnerId = getAssociatedAgentId('owners')
const getCustodianId = getAssociatedAgentId('custodians')

const hasAttribute = getAttr => attr => obj => r.eq(attr, getAttr(obj))
const hasName = hasAttribute(getName)
const hasRecordId = hasAttribute(getRecordId)
const hasPublicKey = hasAttribute(getPublicKey)

const hasBlock = block => obj => {
  return r.and(
    obj('startBlockNum').le(block),
    obj('endBlockNum').gt(block)
  )
}

const queryWithCurrentBlock = query => {
  return r.table('blocks')
    .orderBy(r.desc('blockNum'))
    .nth(0)('blockNum')
    .do(query)
}

const getTable = (tableName, block) =>
      r.table(tableName).filter(hasBlock(block))

const findRecord = recordId => block => {
  return getTable('records', block)
    .filter(hasRecordId(recordId))
    .nth(0)
}

const findProperty = recordId => propertyName => block => {
  return getTable('properties', block)
    .filter(hasRecordId(recordId))
    .filter(hasName(propertyName))
    .nth(0)
}

const getAuthorizedReporterKeys = property => {
  return getReporters(property)
    .filter(getAuthorization)
    .map(getPublicKey)
    .coerceTo('array')
}

const getReporter = publicKey => block => {
  return getTable('agents', block)
    .filter(hasPublicKey(publicKey))
    .pluck('name', 'publicKey')
    .nth(0)
}

const findReportedValues =
      recordId => propertyName => dataType => reporterKeys => block => {
        return getTable('propertyPages', block)
          .filter(hasRecordId(recordId))
          .filter(hasName(propertyName))
          .concatMap(getReportedValues)
          .map(getUpdate(dataType)(reporterKeys)(block))
          .orderBy(r.desc('timestamp'))
          .coerceTo('array')
      }

const getValue = dataType => value => {
  return r.branch(
    r.eq(dataType, 'INT'), value('intValue'),
    r.eq(dataType, 'STRING'), value('stringValue'),
    r.eq(dataType, 'FLOAT'), value('floatValue'),
    r.eq(dataType, 'BYTES'), value('bytesValue'),
    r.eq(dataType, 'LOCATION'), value('locationValue'),
    value('bytesValue') // if dataType is unknown, use bytesValue
  )
}

const getUpdate = dataType => reporterKeys => block => value => {
  return r.expr({
    'value': getValue(dataType)(value),
    'timestamp': value('timestamp'),
    'reporter': getReporter(reporterKeys.nth(value('reporterIndex')))(block)
  })
}

/* Queries */

const fetchPropertyQuery = (recordId, propertyName) => {
  return queryWithCurrentBlock(block => {
    return findProperty(recordId)(propertyName)(block).do(property => {
      return findReportedValues(recordId)(propertyName)(getDataType(property))(getAuthorizedReporterKeys(property))(block).do(values => {
        return r.expr({
          'name': propertyName,
          'recordId': recordId,
          'reporters': getAuthorizedReporterKeys(property),
          'dataType': getDataType(property),
          'value': values.nth(0)('value'),
          'updates': values
        })
      })
    })
  })
}

/* Exported functions */

const fetchProperty = (recordId, propertyName) => {
  return db.runQuery(fetchPropertyQuery(recordId, propertyName))
}

module.exports = {
  fetchProperty
}
