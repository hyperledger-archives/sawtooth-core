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


class _TpResponseError(Exception):
    """Parent class for errors that will be parsed and sent to a validator.

    Args:
        message (str): Standard error message to be logged or sent back
        extended_data (bytes, optional): Byte-encoded data to be parsed later
            by the app developer. Opaque to the validator and Sawtooth.
    """

    def __init__(self, message, extended_data=None):
        super().__init__(message)

        if extended_data is not None and not isinstance(extended_data, bytes):
            raise TypeError("extended_data must be byte-encoded")
        self.extended_data = extended_data


class InvalidTransaction(_TpResponseError):
    """Raised for an Invalid Transaction."""
    pass


class InternalError(_TpResponseError):
    """Raised when an internal error occurs during transaction processing."""
    pass


class AuthorizationException(Exception):
    """Raised when a authorization error occurs."""
    pass


class LocalConfigurationError(Exception):
    """Raised when a log configuraiton error occurs."""
    pass
