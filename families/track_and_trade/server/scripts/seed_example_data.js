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

const _ = require('lodash')
const request = require('request-promise-native')
const { TransactionEncoder } = require('sawtooth-sdk')
const protos = require('../blockchain/protos')

const SERVER = process.env.SERVER || 'http://localhost:3000'
const DATA = process.env.DATA

if (DATA.indexOf('.json') === -1) {
  throw new Error('Use the "DATA" environment variable to specify a JSON file')
}

const { records, agents } = require(`./${DATA}`)
let batcherPubkey = null

const createPayload = message => {
  return protos.TTPayload.encode(_.assign({
    timestamp: Math.floor(Date.now() / 1000)
  }, message)).finish()
}

const createTxn = (privateKey, payload) => {
  return new TransactionEncoder(privateKey, {
    familyName: 'track_and_trade',
    familyVersion: '1.0',
    payloadEncoding: 'application/protobuf',
    inputs: ['1c1108'],
    outputs: ['1c1108'],
    batcherPubkey
  }).create(payload)
}

const createProposal = (privateKey, action) => {
  return createTxn(privateKey, createPayload({
    action: protos.TTPayload.Action.CREATE_PROPOSAL,
    createProposal: protos.CreateProposalAction.create(action)
  }))
}

const answerProposal = (privateKey, action) => {
  return createTxn(privateKey, createPayload({
    action: protos.TTPayload.Action.ANSWER_PROPOSAL,
    answerProposal: protos.AnswerProposalAction.create(action)
  }))
}

const submitTxns = txns => {
  return request({
    method: 'POST',
    url: `${SERVER}/api/transactions?wait`,
    headers: { 'Content-Type': 'application/octet-stream' },
    encoding: null,
    body: new TransactionEncoder(agents[0].privateKey).encode(txns)
  })
  .catch(err => {
    console.error(err.response.body.toString())
    process.exit()
  })
}

protos.compile()
  .then(() => request(`${SERVER}/api/info`))
  .then(res => { batcherPubkey = JSON.parse(res).pubkey })

  // Create Agents
  .then(() => {
    console.log('Creating Agents . . .')
    const agentAdditions = agents.map(agent => {
      return createTxn(agent.privateKey, createPayload({
        action: protos.TTPayload.Action.CREATE_AGENT,
        createAgent: protos.CreateAgentAction.create({ name: agent.name })
      }))
    })

    return submitTxns(agentAdditions)
  })

  // Create Users
  .then(() => {
    console.log('Creating Users . . .')
    const userRequests = agents.map(agent => {
      const user = _.omit(agent, 'name', 'privateKey', 'hashedPassword')
      user.password = agent.hashedPassword
      return request({
        method: 'POST',
        url: `${SERVER}/api/users`,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(user)
      })
    })

    return Promise.all(userRequests)
  })

  // Create Records
  .then(() => {
    console.log('Creating Records . . .')
    const recordAdditions = records.map(record => {
      const properties = record.properties.map(property => {
        if (property.dataType === protos.PropertySchema.DataType.LOCATION) {
          property.locationValue = protos.Location.create(property.locationValue)
        }
        return protos.PropertyValue.create(property)
      })

      return createTxn(agents[record.ownerIndex || 0].privateKey, createPayload({
        action: protos.TTPayload.Action.CREATE_RECORD,
        createRecord: protos.CreateRecordAction.create({
          recordId: record.recordId,
          recordType: record.recordType,
          properties
        })
      }))
    })

    return submitTxns(recordAdditions)
  })

  // Transfer Custodianship
  .then(() => {
    console.log('Transferring Custodianship . . .')
    const custodianProposals = records
      .filter(record => record.custodianIndex !== undefined)
      .map(record => {
        return createProposal(agents[record.ownerIndex || 0].privateKey, {
          recordId: record.recordId,
          receivingAgent: agents[record.custodianIndex].publicKey,
          role: protos.Proposal.Role.CUSTODIAN
        })
      })

    return submitTxns(custodianProposals)
  })
  .then(() => {
    const custodianAnswers = records
      .filter(record => record.custodianIndex !== undefined)
      .map(record => {
        return answerProposal(agents[record.custodianIndex].privateKey, {
          recordId: record.recordId,
          receivingAgent: agents[record.custodianIndex].publicKey,
          role: protos.Proposal.Role.CUSTODIAN,
          response: protos.AnswerProposalAction.Response.ACCEPT
        })
      })

    return submitTxns(custodianAnswers)
  })

  // Authorize New Reporters
  .then(() => {
    console.log('Authorizing New Reporters . . .')
    const reporterProposals = records
      .filter(record => record.reporterIndex !== undefined)
      .map(record => {
        return createProposal(agents[record.ownerIndex || 0].privateKey, {
          recordId: record.recordId,
          receivingAgent: agents[record.reporterIndex].publicKey,
          role: protos.Proposal.Role.REPORTER,
          properties: ['temperature', 'location', 'tilt', 'shock']
        })
      })

    return submitTxns(reporterProposals)
  })
  .then(() => {
    const reporterAnswers = records
      .filter(record => record.reporterIndex !== undefined)
      .map(record => {
        return answerProposal(agents[record.reporterIndex].privateKey, {
          recordId: record.recordId,
          receivingAgent: agents[record.reporterIndex].publicKey,
          role: protos.Proposal.Role.REPORTER,
          response: protos.AnswerProposalAction.Response.ACCEPT
        })
      })

    return submitTxns(reporterAnswers)
  })
