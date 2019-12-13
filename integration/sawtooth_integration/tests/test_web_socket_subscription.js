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
 * ------------------------------------------------------------------------------
 */


var ws = new WebSocket('ws:rest-api:8008/subscriptions');
console.log("WebSocket created");

isEventGood = function(event) {
  try {
    block_num = event.block_num;
    console.log("Got block ", block_num);
    if (block_num == 0) {
      return block_num;
    }
    block_id = event.block_id;
    previous_block_id = event.previous_block_id;
    //
    state_changes = event.state_changes;
    change = state_changes[0]
    type = change.type;
    value = change.value;
    address = change.address;
  } catch(e) {
    console.log(e);
    return -1;
  }
  return block_num;
};

ws.onopen = function(event) {
  ws.send(JSON.stringify({
    'action': 'subscribe',
    'address_prefixes': ['1cf126']
  }));
  console.log("Subscription sent");
};

ws.onmessage = function(event) {
  console.log("Got event");
  console.log(event.data);
  state_delta_event = JSON.parse(event.data);
  block_num = isEventGood(state_delta_event);
  if (block_num == -1) {
    phantom.exit(1);
  }
  if (block_num >= 5) {
    phantom.exit(0);
  }
};
