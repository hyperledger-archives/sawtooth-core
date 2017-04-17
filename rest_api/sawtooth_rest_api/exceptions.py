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


class WrongBodyType(web.HTTPBadRequest):
    def __init__(self):
        message = 'Expected an octet-stream encoded Protobuf binary'
        super().__init__(reason=message)


class EmptyProtobuf(web.HTTPBadRequest):
    def __init__(self):
        message = 'Your submission contained no batches'
        super().__init__(reason=message)


class BadProtobuf(web.HTTPBadRequest):
    def __init__(self):
        message = 'There was a problem decoding your Protobuf binary'
        super().__init__(reason=message)


class BadStatusBody(web.HTTPBadRequest):
    def __init__(self):
        message = 'Expected a json formatted array of id strings'
        super().__init__(reason=message)


class MissingStatusId(web.HTTPBadRequest):
    def __init__(self):
        message = 'At least one batch id must be specified to check status'
        super().__init__(reason=message)


class BadCount(web.HTTPBadRequest):
    def __init__(self):
        message = 'The "count" parameter must be a non-zero integer'
        super().__init__(reason=message)


class ValidatorUnavailable(web.HTTPServiceUnavailable):
    def __init__(self):
        message = 'Could not reach validator, validator timed out'
        super().__init__(reason=message)


class ValidatorDisconnect(web.HTTPServiceUnavailable):
    def __init__(self):
        message = 'The connection to the validator was lost'
        super().__init__(reason=message)
