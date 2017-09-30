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

const _getProp = (record, propName) => {
  return record.properties.find((prop) => prop.name === propName)
}

const getPropertyValue = (record, propName, defaultValue = null) => {
  let prop = _getProp(record, propName)
  if (prop && prop.value) {
    return prop.value
  } else {
    return defaultValue
  }
}

const isReporter = (record, propName, publicKey) => {
  let prop = _getProp(record, propName)
  if (prop) {
    return prop.reporters.indexOf(publicKey) > -1
  } else {
    return false
  }
}

const _getPropTimeByComparison = (compare) => (record) => {
  if (!record.updates.properties) {
    return null
  }

  return Object.values(record.updates.properties)
      .reduce((acc, updates) => acc.concat(updates), [])
      .reduce((selected, update) =>
              compare(selected.timestamp, update.timestamp) ? update : selected)
      .timestamp
}

const getLatestPropertyUpdateTime =
  _getPropTimeByComparison((selected, timestamp) => selected < timestamp)

const getOldestPropertyUpdateTime =
  _getPropTimeByComparison((selected, timestamp) => selected > timestamp)

const countPropertyUpdates = (record) => {
  if (!record.updates.properties) {
    return 0
  }

  return Object.values(record.updates.properties).reduce(
    (sum, updates) => sum + updates.length, 0)
}

module.exports = {
  getPropertyValue,
  isReporter,
  getLatestPropertyUpdateTime,
  getOldestPropertyUpdateTime,
  countPropertyUpdates
}
