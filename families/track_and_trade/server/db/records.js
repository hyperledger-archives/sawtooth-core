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
const getRecordType = getAttribute('recordType')
const getProperties = getAttribute('properties')
const getName = getAttribute('name')
const getFinal = getAttribute('final')
const getPublicKey = getAttribute('publicKey')
const getDataType = getAttribute('dataType')
const getReporters = getAttribute('reporters')
const getAuthorization = getAttribute('authorized')
const getReportedValues = getAttribute('reportedValues')
const getStatus = getAttribute('status')

const getAssociatedAgentId = role => record => record(role).nth(-1)('agentId')
const getOwnerId = getAssociatedAgentId('owners')
const getCustodianId = getAssociatedAgentId('custodians')

const getAssociatedAgents =
      role => record => record(role).orderBy(r.desc('timestamp'))
const getOwners = getAssociatedAgents('owners')
const getCustodians = getAssociatedAgents('custodians')

const hasAttribute = getAttr => attr => obj => r.eq(attr, getAttr(obj))
const hasName = hasAttribute(getName)
const hasRecordId = hasAttribute(getRecordId)
const hasPublicKey = hasAttribute(getPublicKey)
const hasStatus = hasAttribute(getStatus)

const hasBlock = block => obj => {
  return r.and(
    obj('startBlockNum').le(block),
    obj('endBlockNum').gt(block)
  )
}

const getTable = (tableName, block) => {
  return r.table(tableName).filter(hasBlock(block))
}

const getProposals = recordId => receivingAgent => block => {
  return getTable('proposals', block)
    .filter(hasRecordId(recordId))
    .filter(hasStatus('OPEN'))
    .pluck('receivingAgent', 'issuingAgent', 'role', 'properties')
    .coerceTo('array')
}

const findRecord = recordId => block => {
  return getTable('records', block)
    .filter(hasRecordId(recordId))
    .nth(0)
}

const findProperty = recordId => block => propertyName => {
  return getTable('properties', block)
    .filter(hasRecordId(recordId))
    .filter(hasName(propertyName))
    .nth(0)
}

const getReporter = publicKey => block => {
  return getTable('agents', block)
    .filter(hasPublicKey(publicKey))
    .pluck('name', 'publicKey')
    .coerceTo('array')
    .do(results => {
      return r.branch(
        results.isEmpty(),
        { name: 'BAD DATA', publicKey: 'BAD DATA' },
        results(0))
    })
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
    'reporter': getReporter(reporterKeys.map(getPublicKey).nth(value('reporterIndex')))(block)
  })
}

const getTypeProperties = record => block => {
  return getTable('recordTypes', block)
    .filter(hasName(getRecordType(record)))
    .map(getProperties)
    .map(getName)
    .nth(0)
    .map(findProperty(getRecordId(record))(block))
    .coerceTo('array')
}

const getPropertyValues = recordId => block => property => {
  return getReporters(property).do(reporterKeys => {
    return getDataType(property).do(dataType => {
      return r.expr({
        'name': getName(property),
        'dataType': dataType,
        'reporterKeys': reporterKeys,
        'values': findReportedValues(recordId)(getName(property))(dataType)(reporterKeys)(block)
      })
    })
  })
}

const getCurrentValue = propertyValue => {
  return r.branch(
    propertyValue('values').count().eq(0),
    null,
    propertyValue('values').nth(0)
  )
}

const makePropertiesEntry = propertyValues => {
  return propertyValues
    .map(entry => {
      return r.object(
        getName(entry),
        entry('values').pluck('value', 'timestamp')
      )
    })
    .reduce((left, right) => left.merge(right))
    .default({})
}

const getAuthorizedReporterKeys = propertyValue => {
  return propertyValue('reporterKeys')
    .filter(getAuthorization)
    .map(getPublicKey)
    .coerceTo('array')
}

/* Queries */

const fetchPropertyQuery = (recordId, name) => block => {
  return findProperty(recordId)(block)(name).do(property => {
    return getPropertyValues(recordId)(block)(property).do(propertyValues => {
      return r.expr({
        'name': name,
        'recordId': recordId,
        'reporters': getAuthorizedReporterKeys(propertyValues),
        'dataType': propertyValues('dataType'),
        'value': getCurrentValue(propertyValues),
        'updates': propertyValues('values')
      })
    })
  })
}

const _loadRecord = (block, authedKey) => (record) => {
  let recordId = getRecordId(record)
  return getTypeProperties(record)(block)
    .map(getPropertyValues(recordId)(block)).do(propertyValues => {
      return r.expr({
        'recordId': getRecordId(record),
        'owner': getOwnerId(record),
        'custodian': getCustodianId(record),
        'final': getFinal(record),
        'properties': propertyValues
          .map(propertyValue => r.expr({
            'name': getName(propertyValue),
            'type': getDataType(propertyValue),
            'value': getCurrentValue(propertyValue).do(
              value => r.branch(
                value,
                value('value'),
                value
              )
            ),
            'reporters': getAuthorizedReporterKeys(propertyValue),
          })),
        'updates': r.expr({
          'owners': getOwners(record),
          'custodians': getCustodians(record),
          'properties': makePropertiesEntry(propertyValues)
        }),
        'proposals': getProposals(recordId)(authedKey)(block)
      })
    })
}

const fetchRecordQuery = (recordId, authedKey) => block => {
  return findRecord(recordId)(block).do(_loadRecord(block, authedKey))
}

const listRecordsQuery = authedKey => block => {
  return getTable('records', block)
    .map(_loadRecord(block, authedKey))
    .coerceTo('array')
}

/* Exported functions */

const fetchProperty = (recordId, propertyName) => {
  return db.queryWithCurrentBlock(fetchPropertyQuery(recordId, propertyName))
}

const fetchRecord = (recordId, authedKey) => {
  return db.queryWithCurrentBlock(fetchRecordQuery(recordId, authedKey))
}

const listRecords = authedKey => {
  return db.queryWithCurrentBlock(listRecordsQuery(authedKey))
}

module.exports = {
  fetchProperty,
  fetchRecord,
  listRecords
}
