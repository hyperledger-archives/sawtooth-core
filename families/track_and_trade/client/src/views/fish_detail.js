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
    let onsuccess = vnode.attrs.onsuccess || (() => null)
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
                handleSelected(agent.key).then(onsuccess)
              }
            }, m('span.text-truncate',
                 truncate(agent.name, { length: 32 }))))))
    ]
  }
}

const ROLE_TO_ENUM = {
  'owner': payloads.createProposal.enum.OWNER,
  'custodian': payloads.createProposal.enum.CUSTODIAN,
  'reporter': payloads.createProposal.enum.REPORTER
}

const TransferControl = {
  view (vnode) {
    let {record, agents, publicKey, role, label} = vnode.attrs
    if (record.final) {
      return null
    }

    let onsuccess = vnode.attrs.onsuccess || (() => null)
    if (record[role] === publicKey) {
      return [
        m(TransferDropdown, {
          agents,
          handleSelected: _submitProposal(record, ROLE_TO_ENUM[role], onsuccess)
        }, `Transfer ${label}`)
      ]
    } else if (_hasProposal(record, role)) {
      return [
        m('.d-flex.justify-content-start',
          m('button.btn.btn-primary', {
            onclick: (e) => {
              e.preventDefault()
              _answerProposal(record, publicKey, ROLE_TO_ENUM[role],
                              payloads.answerProposal.enum.ACCEPT)

                .then(onsuccess)
            }
          },
          `Accept ${label}`),
          m('button.btn.btn-danger.ml-auto', {
            onclick: (e) => {
              e.preventDefault()
              _answerProposal(record, publicKey, ROLE_TO_ENUM[role],
                              payloads.answerProposal.enum.REJECT)
                .then(onsuccess)
            }
          },
          `Reject`))
      ]
    } else {
      return null
    }
  }
}

const _getProposal = (record, role) =>
  record.proposals.find((proposal) => proposal.role.toLowerCase() === role)

const _hasProposal = (record, role) => !!_getProposal(record, role)

const ReporterControl = {
  view (vnode) {
    let {record, agents, publicKey} = vnode.attrs
    if (record.final) {
      return null
    }

    let onsuccess = vnode.attrs.onsuccess || (() => null)
    if (record.owner === publicKey) {
      return [
        m(AuthorizeReporter, {
          record,
          agents,
          onsubmit: ([publicKey, properties]) =>
          _authorizeReporter(record, publicKey, properties).then(onsuccess)
        })
      ]
    } else if (_hasProposal(record, 'reporter')) {
      let proposal = _getProposal(record, 'reporter')
      return [
        m('.d-flex.justify-content-start',
          m('button.btn.btn-primary', {
            onclick: (e) => {
              e.preventDefault()
              _answerProposal(record, publicKey, ROLE_TO_ENUM['reporter'],
                              payloads.answerProposal.enum.ACCEPT)
                .then(onsuccess)
            }
          },
          `Accept Reporting Authorization for ${proposal.properties}`),
          m('button.btn.btn-danger.ml-auto', {
            onclick: (e) => {
              e.preventDefault()
              _answerProposal(record, publicKey, ROLE_TO_ENUM['reporter'],
                              payloads.answerProposal.enum.REJECT)
                .then(onsuccess)
            }
          },
          `Reject`))
      ]
    } else {
      return null
    }
  }
}

const _agentLink = (agent) =>
  m(`a[href=/agents/${agent.key}]`,
    { oncreate: m.route.link },
    agent.name)

const _propLink = (record, propName, content) =>
  m(`a[href=/properties/${record.recordId}/${propName}]`,
    { oncreate: m.route.link },
    content)

const ReportLocation = {
  view: (vnode) => {
    let onsuccess = vnode.attrs.onsuccess || (() => null)
    return [
      m('form', {
        onsubmit: (e) => {
          e.preventDefault()
          _updateProperty(vnode.attrs.record, {
            name: 'location',
            locationValue: {
              latitude: parseFloat(vnode.state.latitude) * PRECISION,
              longitude: parseFloat(vnode.state.longitude) * PRECISION
            },
            dataType: payloads.updateProperties.enum.LOCATION
          }).then(() => {
            vnode.state.latitude = ''
            vnode.state.longitude = ''
          })
          .then(onsuccess)
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
    ]
  }
}

const ReportValue = {
  view: (vnode) => {
    let onsuccess = vnode.attrs.onsuccess || (() => null)
    let xform = vnode.attrs.xform || ((x) => x)
    return [
      m('form', {
        onsubmit: (e) => {
          e.preventDefault()
          _updateProperty(vnode.attrs.record, {
            name: vnode.attrs.name,
            [vnode.attrs.typeField]: xform(vnode.state.value),
            dataType: vnode.attrs.type
          }).then(() => {
            vnode.state.value = ''
          })
          .then(onsuccess)
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
    _loadData(vnode.attrs.recordId, vnode.state)
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
          m(TransferControl, {
            publicKey,
            record,
            agents: vnode.state.agents,
            role: 'owner',
            label: 'Ownership',
            onsuccess: () => _loadData(vnode.attrs.recordId, vnode.state)
          })),

        _row(
          _labelProperty('Custodian', _agentLink(custodian)),
          m(TransferControl, {
            publicKey,
            record,
            agents: vnode.state.agents,
            role: 'custodian',
            label: 'Custodianship',
            onsuccess: () => _loadData(vnode.attrs.recordId, vnode.state)
          })),

        _row(_labelProperty('Species', getPropertyValue(record, 'species'))),

        _row(
          _labelProperty('Length (cm)', getPropertyValue(record, 'length', 0) / PRECISION),
          _labelProperty('Weight (kg)', getPropertyValue(record, 'weight', 0) / PRECISION)),

        _row(
          _labelProperty(
            'Location',
            _propLink(record, 'location', _formatLocation(getPropertyValue(record, 'location')))
          ),
          (isReporter(record, 'location', publicKey) && !record.final
           ? m(ReportLocation, { record, onsuccess: () => _loadData(record.recordId, vnode.state) })
           : null)),

        _row(
          _labelProperty(
            'Temperature',
            _propLink(record, 'temperature', _formatTemp(getPropertyValue(record, 'temperature')))),
          (isReporter(record, 'temperature', publicKey) && !record.final
          ? m(ReportValue,
            {
              name: 'temperature',
              label: 'Temperature (C°)',
              record,
              typeField: 'intValue',
              type: payloads.updateProperties.enum.INT,
              xform: (x) => parseFloat(x) * PRECISION,
              onsuccess: () => _loadData(vnode.attrs.recordId, vnode.state)
            })
           : null)),

        _row(
          _labelProperty(
            'Tilt',
            _propLink(record, 'tilt', getPropertyValue(record, 'tilt', 'Unknown'))),
          (isReporter(record, 'tilt', publicKey) && !record.final
           ? m(ReportValue, {
             name: 'tilt',
             label: 'Tilt',
             record,
             typeField: 'stringValue',
             type: payloads.updateProperties.enum.STRING,
             onsuccess: () => _loadData(vnode.attrs.recordId, vnode.state)
           })
           : null)),

        _row(
          _labelProperty(
            'Shock',
            _propLink(record, 'shock', getPropertyValue(record, 'shock', 'Unknown'))),
          (isReporter(record, 'shock', publicKey) && !record.final
           ? m(ReportValue, {
             name: 'shock',
             label: 'Shock',
             record,
             typeField: 'stringValue',
             type: payloads.updateProperties.enum.STRING,
             onsuccess: () => _loadData(vnode.attrs.recordId, vnode.state)
           })
           : null)),

        _row(m(ReporterControl, {
          record,
          publicKey,
          agents: vnode.state.agents,
          onsuccess: () => _loadData(vnode.attrs.recordId, vnode.state)
        })),

        ((record.owner === publicKey && !record.final)
         ? m('.row.m-2',
             m('.col.text-center',
               m('button.btn.btn-danger', {
                 onclick: (e) => {
                   e.preventDefault()
                   _finalizeRecord(record).then(() =>
                     _loadData(vnode.attrs.recordId, vnode.state))
                 }
               },
               'Finalize')))
         : '')
       )
    ]
  }
}

const _formatLocation = (location) => {
  if (location && location.latitude !== undefined && location.longitude !== undefined) {
    let latitude = location.latitude / PRECISION
    let longitude = location.longitude / PRECISION
    return `${latitude.toFixed(6)}, ${longitude.toFixed(6)}`
  } else {
    return 'Unknown'
  }
}

const _formatTemp = (temp) => {
  if (temp !== undefined || temp !== null) {
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

const _loadData = (recordId, state) => {
  let publicKey = api.getPublicKey()
  return api.get(`records/${recordId}`)
  .then(record =>
    Promise.all([
      record,
      api.get('agents')]))
  .then(([record, agents, owner, custodian]) => {
    state.record = record
    state.agents = agents.filter((agent) => agent.key !== publicKey)
    state.owner = agents.find((agent) => agent.key === record.owner)
    state.custodian = agents.find((agent) => agent.key === record.custodian)
  })
}

const _submitProposal = (record, role, onsuccess) => (publicKey) => {
  let transferPayload = payloads.createProposal({
    recordId: record.recordId,
    receivingAgent: publicKey,
    role: role
  })

  return transactions.submit([transferPayload], true).then(() => {
    console.log('Successfully submitted proposal')
  })
  .then(onsuccess)
}

const _answerProposal = (record, publicKey, role, response) => {
  let answerPayload = payloads.answerProposal({
    recordId: record.recordId,
    receivingAgent: publicKey,
    role,
    response
  })

  return transactions.submit([answerPayload], true).then(() => {
    console.log('Successfully submitted answer')
  })
}

const _updateProperty = (record, value) => {
  let updatePayload = payloads.updateProperties({
    recordId: record.recordId,
    properties: [value]
  })

  return transactions.submit([updatePayload], true).then(() => {
    console.log('Successfully submitted property update')
  })
}

const _finalizeRecord = (record) => {
  let finalizePayload = payloads.finalizeRecord({
    recordId: record.recordId
  })

  return transactions.submit([finalizePayload], true).then(() => {
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

  return transactions.submit([authroizePayload], true).then(() => {
    console.log('Successfully submitted proposal')
  })
}

module.exports = FishDetail
