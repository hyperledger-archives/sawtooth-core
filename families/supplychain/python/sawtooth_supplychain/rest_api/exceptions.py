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

import json
from aiohttp.web import HTTPError


class RestApiConfigurationError(Exception):
    pass


class _ApiError(HTTPError):
    """A parent class for all REST API errors. Extends aiohttp's HTTPError,
    so instances will be caught automatically be the API, and turned into a
    response to send back to clients. Children should not define any methods,
    just four class variables which the parent __init__ will reference.

    Attributes:
        api_code (int): The fixed code to include in the JSON error response.
            Once established, this code should never change.
        status_code (int): HTTP status to use. Referenced withinin HTTPError's
            __init__ method.
        title (str): A short headline for the error.
        message (str): The human-readable description of the error.

    Raises:
        AssertionError: If api_code, status_code, title, or message were
            not set.
    """
    api_code = None
    status_code = None
    title = None
    message = None

    def __init__(self):
        assert self.api_code is not None, 'Invalid ApiError, api_code not set'
        assert self.status_code is not None, 'Invalid ApiError, status not set'
        assert self.title is not None, 'Invalid ApiError, title not set'
        assert self.message is not None, 'Invalid ApiError, message not set'

        error = {
            'code': self.api_code,
            'title': self.title,
            'message': self.message}

        super().__init__(
            content_type='application/json',
            text=json.dumps(
                {'error': error},
                indent=2,
                separators=(',', ': '),
                sort_keys=True))


class UnknownDatabaseError(_ApiError):
    api_code = 1000
    status_code = 503
    title = 'Unknown Database Error'
    message = ("An unknown error occurred with the database while "
               "processing the request.")


class DatabaseConnectionError(_ApiError):
    api_code = 1001
    status_code = 503
    title = 'Database Connection Error'
    message = ("Can’t connect to the database while processing the request.")


class AgentNotFound(_ApiError):
    api_code = 1010
    status_code = 404
    title = 'Agent Not Found'
    message = ("There is no Agent with the id specified in the database.")


class RecordNotFound(_ApiError):
    api_code = 1011
    status_code = 404
    title = 'Record Not Found'
    message = ("There is no Record with the id specified in the database.")


class InvalidCountQuery(_ApiError):
    api_code = 53
    status_code = 400
    title = 'Invalid Count Query'
    message = ("The ‘count’ parameter must be a positive, non-zero integer.")


class InvalidPagingQuery(_ApiError):
    api_code = 54
    status_code = 400
    title = 'Invalid Paging Query'
    message = ("One or more of the ‘min’, ‘max’, or ‘count’ query "
               "parameters were invalid or out of range. ")


class CountInvalid(_ApiError):
    api_code = 53
    status_code = 400
    title = 'Invalid Count Query'
    message = ("The 'count' query parameter must be a positive, "
               "non-zero integer less than 1000.")


class PagingInvalid(_ApiError):
    api_code = 54
    status_code = 400
    title = 'Invalid Paging Query'
    message = ("Paging request failed as written. One or more of the "
               "'min', 'max', or 'count' query parameters were invalid or "
               "out of range.")
