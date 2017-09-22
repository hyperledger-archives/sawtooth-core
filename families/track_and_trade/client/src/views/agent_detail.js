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

const api = require('../services/api')
const layout = require('../components/layout')

// Basis for info fields with headers
const labeledField = (header, field) => {
  return m('.field-group.mt-5', header, field)
}

const fieldHeader = (label, ...additions) => {
  return m('.field-header', [
    m('span.h5.mr-3', label),
    additions
  ])
}

// Simple info field with a label
const staticField = (label, info) => labeledField(fieldHeader(label), info)

/**
 * Displays information for a particular Agent.
 */
const AgentDetailPage = {
  oninit (vnode) {
    api.get(`agents/${vnode.attrs.publicKey}`)
      .then(agent => { vnode.state.agent = agent })
  },

  view (vnode) {
    const publicKey = _.get(vnode.state, 'agent.publicKey', '')

    return [
      layout.title(_.get(vnode.state, 'agent.name', '')),
      m('.container',
        layout.row(staticField('Public Key', publicKey)))
    ]
  }
}

module.exports = AgentDetailPage
