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

const insert = block => {
  return db.modifyTable('blocks', blocks => {
    return blocks
      .get(block.blockNum)
      .do(foundBlock => {
        return r.branch(foundBlock, foundBlock, blocks.insert(block))
      })
  })
    .then(result => {
      // If the blockNum did not already exist, or had the same id
      // there is no fork, return the block
      if (!result.blockId || result.blockId === block.blockId) {
        return block
      }

      // Otherwise, a fork has occurred, and must be resolved
      return db.modifyTable('blocks', blocks => {
        return blocks
          .filter(r.row('blockNum').ge(block.blockNum))
          .delete()
          .do(() => blocks.insert(block))
      })
        .then(() => block)
    })
}

module.exports = {
  insert
}
