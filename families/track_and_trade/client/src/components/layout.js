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

const m = require('mithril')
const _ = require('lodash')
const octicons = require('octicons')

/**
 * Returns a header styled to be a page title
 */
const title = title => m('h3.text-center.mb-3', title)

/**
 * Returns a row of any number of columns, suitable for placing in a container
 */
const row = columns => {
  if (!_.isArray(columns)) columns = [columns]
  return m('.row', columns.map(col => m('.col-md', col)))
}

/**
 * Returns a mithriled icon from Github's octicon set
 */
const icon = name => m.trust(octicons[name].toSVG())

module.exports = {
  title,
  row,
  icon
}
