# Copyright 2016 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ------------------------------------------------------------------------------

from __future__ import print_function

from sawtooth.cli.stats_lib.stats_utils import ValidatorCommunications


class EndpointManager(object):
    def __init__(self, urls):
        self.validator_contact_attempted = False
        self.validator_responded = False
        self.recent_validator_responded = False

        self.endpoint_urls = list(urls)
        self.endpoints = {}

        self.contact_list = None

        self.validator_comm = ValidatorCommunications()

    def endpoint_discovery_loop(self):
        self.contact_list = list(self.endpoint_urls)
        url = self.contact_list.pop()
        path = url + "/store/{0}/*".format('EndpointRegistryTransaction')
        self.validator_comm.get_request(
            path, self._endpoint_discovery_response,
            self._update_endpoint_continue)

    def _endpoint_discovery_response(self, results, response_code):
        # response has been received
        # if response OK, then get host url & port number of each validator
        # if response not OK, then validator must be busy,
        # try another validator
        if response_code is 200:
            updated_endpoint_urls = []
            self.endpoints = results
            for endpoint in results.values():
                updated_endpoint_urls.append(
                    'http://{0}:{1}'.format(
                        endpoint["Host"], endpoint["HttpPort"]))
            self.endpoint_urls = updated_endpoint_urls
            # if contact is successful, then...
            self.validator_contact_attempted = True
            self.validator_responded = True
            self.recent_validator_responded = True
        else:
            self._update_endpoint_continue(None)

    def _update_endpoint_continue(self, failure):
        # if no response (or did not respond with 200 - see above),
        # then try with another url from the contact list
        if len(self.contact_list) > 0:
            url = self.contact_list.pop()
            path = url + "/store/{0}/*".format('EndpointRegistryTransaction')
            self.validator_comm.get_request(
                path, self._endpoint_discovery_response,
                self._update_endpoint_continue)
        else:
            # contact with all validators has been attempted
            # no validator has responded
            self.validator_contact_attempted = True
            self.recent_validator_responded = False

    def endpoint_loop_stop(self, reason):
        print("handling endpoint loop stop")
        return reason

    def update_endpoint_loop_error(self, reason):
        print("handling endpoint loop error")
        return reason
