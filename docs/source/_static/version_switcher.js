/**
 * Copyright 2016, 2017 Intel Corporation
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
 * ------------------------------------------------------------------------------
 */

var VERSION_URL = 'https://sawtooth.hyperledger.org/docs/versions.json';
var versionRequest = new XMLHttpRequest();
var versionSwitcher = document.getElementById('version_switcher');

versionSwitcher.onchange = function() {
  if (this.value) {
    window.location.assign(this.value);
  }
};

versionRequest.onreadystatechange = function() {
  if (!versionSwitcher.length && versionRequest.responseText) {
    var versions = JSON.parse(versionRequest.responseText);
    versions.forEach(function(versionTuple) {
      var option = document.createElement('option');
      option.innerText = versionTuple[0];
      option.value = versionTuple[1];
      versionSwitcher.appendChild(option);
      if (window.location.href === option.value) {
        option.selected = true;
      }
    });
  }
};

versionRequest.open('GET', VERSION_URL, true);
versionRequest.send(null);
