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

/**
 * Returns an input field which modifies a particular value in state
 */
const input = (type, onValue, label, required = true) => {
  return m('.form-group', [
    m('label', label),
    m('input.form-control', {
      type,
      required,
      oninput: m.withAttr('value', onValue)
    })
  ])
}

const textInput = _.partial(input, 'text')
const passwordInput = _.partial(input, 'password')
const numberInput = _.partial(input, 'number')
const emailInput = _.partial(input, 'email')

/**
 * Convenience function for returning partial onValue functions
 */
const stateSetter = state => key => value => { state[key] = value }

module.exports = {
  input,
  textInput,
  passwordInput,
  numberInput,
  emailInput,
  stateSetter
}
