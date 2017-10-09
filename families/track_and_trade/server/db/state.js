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

const _ = require('lodash')
const r = require('rethinkdb')
const db = require('./')

const addBlockState = (tableName, indexName, indexValue, doc, blockNum) => {
  return db.modifyTable(tableName, table => {
    return table
      .getAll(indexValue, { index: indexName })
      .filter({ endBlockNum: Number.MAX_SAFE_INTEGER })
      .coerceTo('array')
      .do(oldDocs => {
        return oldDocs
          .filter({ startBlockNum: blockNum })
          .coerceTo('array')
          .do(duplicates => {
            return r.branch(
              // If there are duplicates, do nothing
              duplicates.count().gt(0),
              duplicates,

              // Otherwise, update the end block on any old docs,
              // and insert the new one
              table
                .getAll(indexValue, { index: indexName })
                .update({ endBlockNum: blockNum })
                .do(() => {
                  return table.insert(_.assign({}, doc, {
                    startBlockNum: blockNum,
                    endBlockNum: Number.MAX_SAFE_INTEGER
                  }))
                })
            )
          })
      })
  })
}

const addAgent = (agent, blockNum) => {
  return addBlockState('agents', 'publicKey', agent.publicKey,
                       agent, blockNum)
}

const addRecord = (record, blockNum) => {
  return addBlockState('records', 'recordId', record.recordId,
                       record, blockNum)
}

const addRecordType = (type, blockNum) => {
  return addBlockState('recordTypes', 'name', type.name,
                       type, blockNum)
}

const addProperty = (property, blockNum) => {
  return addBlockState('properties', 'attributes',
                       ['name', 'recordId'].map(k => property[k]),
                       property, blockNum)
}

const addPropertyPage = (page, blockNum) => {
  return addBlockState('propertyPages', 'attributes',
                       ['name', 'recordId', 'pageNum'].map(k => page[k]),
                       page, blockNum)
}

const addProposal = (proposal, blockNum) => {
  return addBlockState(
    'proposals', 'attributes',
    ['recordId', 'timestamp', 'receivingAgent', 'role'].map(k => proposal[k]),
    proposal, blockNum)
}

module.exports = {
  addAgent,
  addRecord,
  addRecordType,
  addProperty,
  addPropertyPage,
  addProposal
}
