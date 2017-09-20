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

/**
 * A simple navbar wrapper, which displays children in the responsive collapse.
 */
const Navbar = {
  view (vnode) {
    return m('nav.navbar.navbar-expand-sm.navbar-dark.bg-dark.mb-5', [
      m('a.navbar-brand[href="/"]', { oncreate: m.route.link }, 'FishNet'),
      m('button.navbar-toggler', {
        type: 'button',
        'data-toggle': 'collapse',
        'data-target': '#navbar',
        'aria-controls': 'navbar',
        'aria-expanded': 'false',
        'aria-label': 'Toggle navigation'
      }, m('span.navbar-toggler-icon')),
      m('#navbar.collapse.navbar-collapse', vnode.children)
    ])
  }
}

/**
 * Creates a list of left-aligned navbar links from href/label tuples.
 */
const links = items => {
  return m('ul.navbar-nav.mr-auto', items.map(([href, label]) => {
    return m('li.nav-item', [
      m('a.nav-link', { href, oncreate: m.route.link }, label)
    ])
  }))
}

/**
 * Creates a single link for use in a navbar.
 */
const link = (href, label) => {
  return m('.navbar-nav', [
    m('a.nav-link', { href, oncreate: m.route.link }, label)
  ])
}

/**
 * Creates a navigation button styled for use in the navbar.
 */
const button = (href, label) => {
  return m('a.btn.btn-outline-primary.my-2.my-sm-0', {
    href,
    oncreate: m.route.link
  }, label)
}

module.exports = {
  Navbar,
  link,
  links,
  button
}
