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

const STORAGE_KEY = 'tnt.authorization'
let authToken = null

/**
 * Getters and setters to handle the auth token both in memory and storage
 */
const getAuth = () => {
  if (!authToken) {
    authToken = localStorage.getItem(STORAGE_KEY)
  }
  return authToken
}

const setAuth = token => {
  localStorage.setItem(STORAGE_KEY, token)
  authToken = token
  return authToken
}

const clearAuth = () => {
  const token = getAuth()
  localStorage.clear(STORAGE_KEY)
  authToken = null
  return token
}

/**
 * Submits a request to an api endpoint with an auth header if present
 */
const request = (method, endpoint, data) => {
  const Authorization = getAuth()
  return m.request({
    method,
    url: `../api/${endpoint}`,
    headers: Authorization ? { Authorization } : {},
    data
  })
}

const get = _.partial(request, 'GET')
const post = _.partial(request, 'POST')
const patch = _.partial(request, 'PATCH')

module.exports = {
  getAuth,
  setAuth,
  clearAuth,
  request,
  get,
  post,
  patch
}
