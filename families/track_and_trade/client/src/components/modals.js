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
const $ = require('jquery')

/**
 * A basic Bootstrap modal. Requires at least a title and body be set in
 * attributes. Also accepts text and functions for accepting/canceling.
 */
const BasicModal = {
  view (vnode) {
    // Set default accept/cancel values
    const acceptText = vnode.attrs.acceptText || 'Accept'
    const cancelText = vnode.attrs.cancelText || 'Cancel'
    const acceptFn = vnode.attrs.acceptFn || _.identity
    const cancelFn = vnode.attrs.cancelFn || _.identity

    return m('.modal.fade#modal', {
      tabindex: '-1',
      role: 'dialog',
      'aria-labelby': 'modal'
    }, [
      m('.modal-dialog', { role: 'document' },
        m('form',
          m('.modal-content',
            m('.modal-header',
              m('h5.modal-title', vnode.attrs.title),
              m('button.close', {
                type: 'button',
                onclick: cancelFn,
                'data-dismiss': 'modal',
                'aria-label': 'Close'
              }, m('span', { 'aria-hidden': 'true' }, m.trust('&times;')))
              ),
            m('.modal-body', vnode.attrs.body),
            m('.modal-footer',
              m('button.btn.btn-secondary', {
                type: 'button',
                onclick: cancelFn,
                'data-dismiss': 'modal'
              }, cancelText),
              m('button.btn.btn-primary', {
                type: 'submit',
                onclick: acceptFn,
                'data-dismiss': 'modal'
              }, acceptText)))))
    ])
  }
}

/**
 * Renders/shows a modal component, with attributes, returning a promise.
 * On close, unmounts the component and resolves/rejects the promise,
 * with rejection indicating the cancel button was pressed.
 */
const show = (modal, attrs, children) => {
  let acceptFn = null
  let cancelFn = null
  const onClosePromise = new Promise((resolve, reject) => {
    acceptFn = resolve
    cancelFn = reject
  })

  const container = document.getElementById('modal-container')
  m.render(container,
           m(modal, _.assign(attrs, { acceptFn, cancelFn }, children)))
  const $modal = $('#modal')
  $modal.on('hidden.bs.modal', () => m.mount(container, null))
  $modal.modal('show')

  return onClosePromise
}

module.exports = {
  BasicModal,
  show
}
