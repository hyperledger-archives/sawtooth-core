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

const express = require('express')
const bodyParser = require('body-parser')

const state = require('../db/state')
const auth = require('./auth')
const users = require('./users')
const { Unauthorized } = require('./errors')

const router = express.Router()
router.use(bodyParser.json({ type: 'application/json' }))

// Adds an object to the request for storing internally generated parameters
const initInternalParams = (req, res, next) => {
  req.internal = {}
  next()
}

// Passes a request's body to a function,
// then sends back the promised result as JSON.
// Will catch errors and send to Express middleware.
const handle = func => (req, res, next) => {
  func(req.body)
    .then(result => res.json(result))
    .catch(err => next(err))
}

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
router.use(initInternalParams)
router.use(authHandler)

router.get('/', (req, res) => {
  state.query(state => state.filter({name: 'message'}))
    .then(messages => res.json(messages[0].value))
})

router.post('/authorization', handle(auth.authorize))

router.post('/users', handle(users.create))

router.use(errorHandler)

module.exports = router
