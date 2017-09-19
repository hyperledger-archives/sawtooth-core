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

const Dashboard = {
  view (vnode) {
    return [
      m('.header.text-center.mb-4',
        m('h4', 'Welcome To'),
        m('h1.mb-3', 'FishNet'),
        m('h5',
          m('em',
            'Powered by ',
            m('strong', 'Sawtooth: Track and Trade')))),
      m('.blurb',
        m('p',
          m('em', 'Track and Trade'),
          ' is a general purpose supply chain solution built using the ',
          'power of ',
          m('a[href="https://github.com/hyperledger/sawtooth-core"]',
            { target: '_blank' },
            "Hyperledger Sawtooth's"),
          ' blockchain technology. It maintains a distributed ledger ',
          'that tracks both asset provenance and a timestamped history ',
          'detailing how an asset was stored, handled, and transported.'),
        m('p',
          m('em', 'FishNet'),
          ' demonstrates this unique technology with an illustrative ',
          'example: tracking the provenance of fish from catch to plate. ',
          'One day an application like this could be used by restaurants, ',
          'grocery stores, and their customers to ensure the fish they ',
          'purchase is ethically sourced and properly transported.'),
        m('p',
          'To use ',
          m('em', 'FishNet'),
          ', create an account using the link in the navbar above. ',
          'Once logged in, you will be able to add new fish assets to ',
          'the blockchain and track them with data like temperature or ',
          'location. You will be able to authorize other "agents" on the ',
          'blockchain to track this data as well, or even transfer ',
          'ownership or possession of the fish entirely. For the ',
          'adventurous, these actions can also be accomplished directly ',
          'with the REST API running on the ',
          m('em', 'Track and Trade'),
          ' server, perfect for automated IoT sensors.'))
    ]
  }
}

module.exports = Dashboard
