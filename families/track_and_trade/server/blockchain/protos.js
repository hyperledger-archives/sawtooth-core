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

const path = require('path')
const _ = require('lodash')
const protobuf = require('protobufjs')

const protos = {}

const loadProtos = (filename, protoNames) => {
  const protoPath = path.resolve(__dirname, '../../protos', filename)
  return protobuf.load(protoPath)
    .then(root => {
      protoNames.forEach(name => {
        protos[name] = root.lookupType(name)
      })
    })
}

const compile = () => {
  return Promise.all([
    loadProtos('agent.proto', [
      'Agent',
      'AgentContainer'
    ]),
    loadProtos('property.proto', [
      'Property',
      'PropertyContainer',
      'PropertyPage',
      'PropertyPageContainer',
      'PropertySchema',
      'PropertyValue',
      'Location'
    ]),
    loadProtos('proposal.proto', [
      'Proposal',
      'ProposalContainer'
    ]),
    loadProtos('record.proto', [
      'Record',
      'RecordContainer',
      'RecordType',
      'RecordTypeContainer'
    ]),
    loadProtos('payload.proto', [
      'TTPayload',
      'CreateAgentAction',
      'FinalizeRecordAction',
      'CreateRecordAction',
      'CreateRecordTypeAction',
      'UpdatePropertiesAction',
      'CreateProposalAction',
      'AnswerProposalAction',
      'RevokeReporterAction'
    ])
  ])
}

module.exports = _.assign(protos, { compile })
