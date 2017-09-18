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
const express = require('express')
const bodyParser = require('body-parser')

const auth = require('./auth')
const blockchain = require('../blockchain/')
const users = require('./users')
const { Unauthorized } = require('./errors')
const agents = require('../db/agents')
const state = require('../db/state')


const router = express.Router()
router.use(bodyParser.json({ type: 'application/json' }))
router.use(bodyParser.raw({ type: 'application/octet-stream' }))

// Logs basic request information to the console
const logRequest = (req, res, next) => {
  console.log(`Received ${req.method} request for ${req.url} from ${req.ip}`)
  next()
}

// Adds an object to the request for storing internally generated parameters
const initInternalParams = (req, res, next) => {
  req.internal = {}
  next()
}

// Passes a request to a function, then sends back the promised result as JSON.
// Will catch errors and send on to any error handling middleware.
const handlePromisedResponse = func => (req, res, next) => {
  func(req)
    .then(result => res.json(result))
    .catch(err => next(err))
}

// Handler suitable for all GET requests. Passes the endpoint function
// a merged copy of the parameters for a request, handling promised results
const handle = func => handlePromisedResponse(req => {
  return func(_.assign({}, req.query, req.params, req.internal))
})

// Handler suitable for POST/PATCH request, passes along the request's body
// in addition to its other parameters.
const handleBody = func => handlePromisedResponse(req => {
  return func(req.body, _.assign({}, req.query, req.params, req.internal))
})

// Check the Authorization header if present.
// Saves the encoded public key to the request object.
const authHandler = (req, res, next) => {
  req.internal.authedKey = null
  const token = req.headers.authorization
  if (!token) return next()

  auth.verifyToken(token)
    .then(publicKey => {
      req.internal.authedKey = publicKey
      next()
    })
    .catch(() => next())
}

// Route-specific middleware, throws error if not authorized
const restrict = (req, res, next) => {
  if (req.internal.authedKey) return next()
  next(new Unauthorized('This route requires a valid Authorization header'))
}

// Send back a simple JSON error with an HTTP status code
const errorHandler = (err, req, res, next) => {
  if (err) {
    res.status(err.status || 500).json({ error: err.message })
  } else {
    next()
  }
}

// Setup routes and custom middleware
router.use(logRequest)
router.use(initInternalParams)
router.use(authHandler)

router.get('/agents', handle(agents.list))

router.get('/', (req, res) => {
  state.query(state => state.filter({name: 'message'}))
    .then(messages => res.json(messages[0].value))
})

router.post('/transactions', restrict, handleBody(blockchain.submit))

router.post('/authorization', handleBody(auth.authorize))

// This route is redundant, but matches RESTful expectations
router.patch('/users/:publicKey', restrict, handleBody((body, params) => {
  if (params.publicKey !== params.authedKey) {
    throw new Unauthorized('You may only modify your own user account!')
  }
  return users.update(body, params)
}))

router.route('/users')
  .post(handleBody(users.create))
  .patch(restrict, handleBody(users.update))

router.use(errorHandler)

module.exports = router
