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

const forms = require('../components/forms')
const api = require('../services/api')
const transactions = require('../services/transactions')
const payloads = require('../services/payloads')

const passwordCard = state => {
  const setter = forms.stateSetter(state)
  const validator = forms.validator(
    () => state.password === state.confirm,
    'Passwords do not match',
    'confirm'
  )
  const passwordField = (id, placeholder) => {
    return forms.field(
      // Run both state setting and validation on value changes
      _.flow(setter(id), validator),
      {
        id,
        placeholder,
        type: 'password',
        class: 'border-warning'
      }
    )
  }

  return forms.group('Password', [
    m('.card.text-center.border-warning',
      m('.card-header.text-white.bg-warning', m('em', m('strong', 'WARNING!'))),
      m('.card-body.text-warning.bg-light',
        m('p.card-text',
          'This password will be used as a secret key to encrypt important ',
          'account information. Although it can be changed later, ',
          m('em',
            'if lost or forgotten it will be ',
            m('strong', 'impossible'),
            ' to recover your account.')),
        m('p.card-text', 'Keep it secure.'),
        passwordField('password', 'Enter password...'),
        passwordField('confirm', 'Confirm password...')))
  ])
}

const userSubmitter = state => e => {
  e.preventDefault()

  const keys = transactions.makePrivateKey(state.password)
  const user = _.assign(keys, _.pick(state, 'username', 'email'))
  user.password = api.hashPassword(state.password)
  const agent = payloads.createAgent(_.pick(state, 'name'))

  transactions.submit(agent, true)
    .then(() => api.post('users', user))
    .then(res => api.setAuth(res.authorization))
    .then(() => m.route.set('/'))
}

/**
 * The Form for authorizing an existing user.
 */
const SignupForm = {
  view (vnode) {
    const setter = forms.stateSetter(vnode.state)

    return m('.signup-form', [
      m('form', { onsubmit: userSubmitter(vnode.state) },
      m('legend', 'Create Agent'),
      forms.textInput(setter('name'), 'Name'),
      forms.emailInput(setter('email'), 'Email'),
      forms.textInput(setter('username'), 'Username'),
      passwordCard(vnode.state),
      m('.container.text-center',
        'Or you can ',
        m('a[href="/login"]',
          { oncreate: m.route.link },
          'login an existing Agent')),
      m('.form-group',
        m('.row.justify-content-end.align-items-end',
          m('col-2',
            m('button.btn.btn-primary',
              'Create Agent')))))
    ])
  }
}

module.exports = SignupForm
