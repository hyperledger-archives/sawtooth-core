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
const db = require('../db')

const router = express.Router()

// Send back a simple JSON error with an HTTP status code
const errorHandler = (err, req, res, next) => {
  if (err) {
    res.status(err.status || 500).json({ error: err.message })
  } else {
    next()
  }
}

// Routes
router.get('/', (req, res) => {
  db.queryState(state => state.filter({name: 'message'}))
    .then(messages => res.json(messages[0].value))
})

router.use(errorHandler)

module.exports = router
