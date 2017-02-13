# Copyright 2017 Intel Corporation
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

from aiohttp import web
from sawtooth_rest_api.protobuf import client_pb2 as client


class _ErrorTrap(object):
    """
    ErrorTraps are particular handlers for a common pattern the REST API
    encounters: translating Protobuf statuses sent over ZMQ, into HTTP errors
    to be raised and sent to the client. Traps take a status as a "trigger"
    (either hard-coded or at instantiation), and provide a "check" method
    which will check the trigger against a status, raising a preset
    HTTP Error if there is a match.

    Args:
        trigger: a Protobuf enum status to match against
        error: the type of error to raise
        message: a message raise the error with
    """
    def __init__(self, trigger, error, message=None):
        self._trigger = trigger
        self._error = error(reason=message)

    def check(self, status):
        if status == self._trigger:
            raise self._error


class Unknown(_ErrorTrap):
    def __init__(self, trigger):
        error = web.HTTPInternalServerError
        message = 'An unknown error occured with your request'
        super().__init__(trigger, error, message)


class NotReady(_ErrorTrap):
    def __init__(self, trigger):
        error = web.HTTPServiceUnavailable
        message = 'The validator is not yet ready to be queried'
        super().__init__(trigger, error, message)


class MissingHead(_ErrorTrap):
    def __init__(self, trigger):
        error = web.HTTPNotFound
        message = 'There is no block with that head id'
        super().__init__(trigger, error, message)


class MissingLeaf(_ErrorTrap):
    def __init__(self):
        super().__init__(
            trigger=client.ClientStateGetResponse.NO_RESOURCE,
            error=web.HTTPNotFound,
            message='There is no leaf at that address')


class MissingBlock(_ErrorTrap):
    def __init__(self):
        super().__init__(
            trigger=client.ClientBlockGetResponse.NO_RESOURCE,
            error=web.HTTPNotFound,
            message='There is no block with that id')


class BadAddress(_ErrorTrap):
    def __init__(self):
        super().__init__(
            trigger=client.ClientStateGetResponse.INVALID_ADDRESS,
            error=web.HTTPBadRequest,
            message='Expected a leaf address, but received a subtree instead')
