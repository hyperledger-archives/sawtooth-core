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
const moment = require('moment')
const truncate = require('lodash/truncate')

const {MultiSelect} = require('../components/forms')
const payloads = require('../services/payloads')
const transactions = require('../services/transactions')
const api = require('../services/api')
const {
  getPropertyValue,
  getLatestPropertyUpdateTime,
  getOldestPropertyUpdateTime,
  isReporter
} = require('../utils/records')

const PRECISION = payloads.FLOAT_PRECISION
/**
 * Possible selection options
 */
const authorizableProperties = [
  ['location', 'Location'],
  ['temperature', 'Temperature'],
  ['tilt', 'Tilt'],
  ['shock', 'Shock']
]

const _labelProperty = (label, value) => [
  m('dl',
    m('dt', label),
    m('dd', value))
]

const _row = (...cols) =>
  m('.row',
    cols
    .filter((col) => col !== null)
    .map((col) => m('.col', col)))

const TransferDropdown = {
  view (vnode) {
    // Default to no-op
    let handleSelected = vnode.attrs.handleSelected || (() => null)
    return [
      m('.dropdown',
        m('button.btn.btn-primary.btn-block.dropdown-toggle.text-left',
          { 'data-toggle': 'dropdown' },
          vnode.children),
        m('.dropdown-menu',
          vnode.attrs.agents.map(agent =>
            m("a.dropdown-item[href='#']", {
              onclick: (e) => {
                e.preventDefault()
                handleSelected(agent.key)
              }
            }, m('span.text-truncate',
                 truncate(agent.name, { length: 32 }))))))
    ]
  }
}

const _agentLink = (agent) =>
  m(`a[href=/agents/${agent.key}]`,
    { oncreate: m.route.link },
    agent.name)

const ReportLocation = {
  view: (vnode) =>
    m('form', {
      onsubmit: (e) => {
        e.preventDefault()
        _updateProperty(vnode.attrs.record, {
          name: 'location',
          locationValue: {
            latitude: parseFloat(vnode.state.latitude),
            longitude: parseFloat(vnode.state.longitude)
          },
          dataType: payloads.updateProperties.enum.LOCATION
        })
      }
    },
    m('.form-row',
      m('.form-group.col-5',
        m('label.sr-only', { 'for': 'latitude' }, 'Latitude'),
        m("input.form-control[type='text']", {
          name: 'latitude',
          onchange: m.withAttr('value', (value) => {
            vnode.state.latitude = value
          }),
          value: vnode.state.latitude,
          placeholder: 'Latitude'
        })),

      m('.form-group.col-5',
        m('label.sr-only', { 'for': 'longitude' }, 'Longitude'),
        m("input.form-control[type='text']", {
          name: 'longitude',
          onchange: m.withAttr('value', (value) => {
            vnode.state.longitude = value
          }),
          value: vnode.state.longitude,
          placeholder: 'Longitude'
        })),

      m('.col-2',
        m('button.btn.btn-primary', 'Update'))))
}

const ReportValue = {
  view: (vnode) => {
    let xform = vnode.attrs.xform || ((x) => x)
    return [
      m('form', {
        onsubmit: (e) => {
          e.preventDefault()
          _updateProperty(vnode.attrs.record, {
            name: vnode.attrs.name,
            [vnode.attrs.typeField]: xform(vnode.state.value),
            dataType: vnode.attrs.type
          })
        }
      },
        m('.form-row',
          m('.form-group.col-10',
            m('label.sr-only', { 'for': vnode.attrs.name }, vnode.attrs.label),
            m("input.form-control[type='text']", {
              name: vnode.attrs.name,
              onchange: m.withAttr('value', (value) => {
                vnode.state.value = value
              }),
              value: vnode.state.value,
              placeholder: vnode.attrs.label
            })),
         m('.col-2',
           m('button.btn.btn-primary', 'Update'))))
    ]
  }
}

const AuthorizeReporter = {
  oninit (vnode) {
    vnode.state.properties = []
  },

  view (vnode) {
    return [
      _row(m('strong', 'Authorize Reporter')),
      m('.row',
        m('.col-6',
          m('input.form-control', {
            type: 'text',
            placeholder: 'Add Reporter Private Key',
            value: vnode.state.reporter,
            oninput: m.withAttr('value', (value) => {
              vnode.state.reporter = value
              let reporter = vnode.attrs.agents.find(
                (agent) => agent.name === value || agent.key === value)
              if (reporter) {
                vnode.state.reporterKey = reporter.key
              }
            })
          })),

        m('.col-4',
          m(MultiSelect, {
            label: 'Select Fields',
            color: 'primary',
            options: authorizableProperties,
            selected: vnode.state.properties,
            onchange: (selection) => {
              vnode.state.properties = selection
            }
          })),

        m('.col-2',
          m('button.btn.btn-primary',
            {
              disabled: (!vnode.state.reporterKey || vnode.state.properties.length === 0),
              onclick: (e) => {
                e.preventDefault()
                vnode.attrs.onsubmit([vnode.state.reporterKey, vnode.state.properties])
                vnode.state.reporterKey = null
                vnode.state.reporter = null
                vnode.state.properties = []
              }
            },
            'Authorize')))
    ]
  }
}

const FishDetail = {
  oninit (vnode) {
    let publicKey = api.getPublicKey()
    api.get(`records/${vnode.attrs.recordId}`)
    .then(record =>
      Promise.all([
        record,
        api.get('agents')]))
    .then(([record, agents, owner, custodian]) => {
      vnode.state.record = record
      vnode.state.agents = agents.filter((agent) => agent.key !== publicKey)
      vnode.state.owner = agents.find((agent) => agent.key === record.owner)
      vnode.state.custodian = agents.find((agent) => agent.key === record.custodian)
    })
  },

  view (vnode) {
    if (!vnode.state.record) {
      return m('.alert-warning', `Loading ${vnode.attrs.recordId}`)
    }

    let publicKey = api.getPublicKey()
    let owner = vnode.state.owner
    let custodian = vnode.state.custodian
    let record = vnode.state.record
    return [
      m('.fish-detail',
        m('h1.text-center', record.recordId),
        _row(
          _labelProperty('Created',
                         _formatTimestamp(getOldestPropertyUpdateTime(record))),
          _labelProperty('Updated',
                         _formatTimestamp(getLatestPropertyUpdateTime(record)))),

        _row(
          _labelProperty('Owner', _agentLink(owner)),
          (owner.key === publicKey && !record.final
           ? m(TransferDropdown, {
             agents: vnode.state.agents,
             handleSelected: _doTransfer(record, payloads.createProposal.enum.OWNER)
           }, 'Transfer Ownership')
           : null)),

        _row(
            _labelProperty('Custodian', _agentLink(custodian)),
          (custodian.key === publicKey && !record.final
           ? m(TransferDropdown, {
             agents: vnode.state.agents,
             handleSelected: _doTransfer(record, payloads.createProposal.enum.CUSTODIAN)
           }, 'Transfer Custodianship')
           : null)),

        _row(_labelProperty('Species', getPropertyValue(record, 'species'))),

        _row(
          _labelProperty('Length (cm)', getPropertyValue(record, 'length', 0) / PRECISION),
          _labelProperty('Weight (kg)', getPropertyValue(record, 'weight', 0) / PRECISION)),

        _row(
          _labelProperty('Location', _formatLocation(getPropertyValue(record, 'location'))),
          (isReporter(record, 'location', publicKey) && !record.final
           ? m(ReportLocation, { record })
           : null)),

        _row(
          _labelProperty('Temperature', _formatTemp(getPropertyValue(record, 'temperature'))),
          (isReporter(record, 'temperature', publicKey) && !record.final
          ? m(ReportValue,
            {
              name: 'temperature',
              label: 'Temperature (C°)',
              record,
              typeField: 'intValue',
              type: payloads.updateProperties.enum.INT,
              xform: (x) => parseInt(x)
            })
           : null)),

        _row(
          _labelProperty('Tilt', getPropertyValue(record, 'tilt', 'Unknown')),
          (isReporter(record, 'tilt', publicKey) && !record.final
           ? m(ReportValue, {
             name: 'tilt',
             label: 'Tilt',
             record,
             typeField: 'stringValue',
             type: payloads.updateProperties.enum.STRING
           })
           : null)),

        _row(
          _labelProperty('Shock', getPropertyValue(record, 'shock', 'Unknown')),
          (isReporter(record, 'shock', publicKey) && !record.final
           ? m(ReportValue, {
             name: 'shock',
             label: 'Shock',
             record,
             typeField: 'stringValue',
             type: payloads.updateProperties.enum.STRING
           })
           : null)),

        ((record.owner === publicKey && !record.final)
         ? m(AuthorizeReporter, {
           record,
           agents: vnode.state.agents,
           onsubmit: ([publicKey, properties]) =>
           _authorizeReporter(record, publicKey, properties)
         })
         : null),

        ((record.owner === publicKey && !record.final)
         ? m('.row.m-2',
             m('.col.text-center',
               m('button.btn.btn-danger', {
                 onclick: (e) => {
                   e.preventDefault()
                   _finalizeRecord(record)
                 }
               },
               'Finalize')))
         : '')
       )
    ]
  }
}

const _formatLocation = (location) => {
  if (location && location.latitude && location.longitude) {
    let latitude = location.latitude / PRECISION
    let longitude = location.longitude / PRECISION
    return `${latitude.toFixed(6)}, ${longitude.toFixed(6)}`
  } else {
    return 'Unknown'
  }
}

const _formatTemp = (temp) => {
  if (temp) {
    return `${(temp / PRECISION).toFixed(6)} C°`
  }

  return 'Unknown'
}

const _formatTimestamp = (sec) => {
  if (!sec) {
    sec = Date.now() / 1000
  }
  return moment.unix(sec).format('YYYY-MM-DD')
}

const _doTransfer = (record, role) => (publicKey) => {
  let transferPayload = payloads.createProposal({
    recordId: record.recordId,
    receivingAgent: publicKey,
    role: role
  })

  transactions.submit([transferPayload]).then(() => {
    console.log('Successfully submitted proposal')
  })
}

const _updateProperty = (record, value) => {
  let updatePayload = payloads.updateProperties({
    recordId: record.recordId,
    properties: [value]
  })

  transactions.submit([updatePayload]).then(() => {
    console.log('Successfully submitted property update')
  })
}

const _finalizeRecord = (record) => {
  let finalizePayload = payloads.finalizeRecord({
    recordId: record.recordId
  })

  transactions.submit([finalizePayload]).then(() => {
    console.log('finalized')
  })
}

const _authorizeReporter = (record, reporterKey, properties) => {
  let authroizePayload = payloads.createProposal({
    recordId: record.recordId,
    receivingAgent: reporterKey,
    role: payloads.createProposal.enum.REPORTER,
    properties: properties
  })

  transactions.submit([authroizePayload]).then(() => {
    console.log('Successfully submitted proposal')
  })
}

module.exports = FishDetail
