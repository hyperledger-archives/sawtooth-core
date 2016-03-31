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
"""
The Common module defines utility methods used across gossip.
"""

import json
import logging
from collections import OrderedDict

import cbor

logger = logging.getLogger(__name__)

NullIdentifier = '0' * 16


def pretty_print_dict(input):
    """Generates a pretty-print formatted version of the input JSON.

    Args:
        input (str): the JSON string to format.

    Returns:
        str: pretty-print formatted string.
    """
    return json.dumps(_ascii_encode_dict(input), indent=2, sort_keys=True)


def json2dict(input):
    """Deserializes JSON into a dictionary.

    Args:
        input (str): the JSON string to deserialize.

    Returns:
        dict: a dictionary object reflecting the structure of the JSON.
    """
    return _ascii_encode_dict(json.loads(input))


def dict2json(input):
    """Serializes a dictionary into JSON.

    Args:
        input (dict): a dictionary object to serialize into JSON.

    Returns:
        str: a JSON string reflecting the structure of the input dict.
    """
    return json.dumps(_ascii_encode_dict(input))


def cbor2dict(input):
    """Deserializes CBOR into a dictionary.

    Args:
        input (bytes): the CBOR object to deserialize.

    Returns:
        dict: a dictionary object reflecting the structure of the CBOR.
    """

    return _ascii_encode_dict(cbor.loads(input))


def dict2cbor(input):
    """Serializes a dictionary into CBOR.

    Args:
        input (dict): a dictionary object to serialize into CBOR.

    Returns:
        bytes: a CBOR object reflecting the structure of the input dict.
    """

    return cbor.dumps(_unicode_encode_dict(input), sort_keys=True)


def _ascii_encode_dict(input):
    """
    Support method to ensure that JSON is converted to ascii since unicode
    identifiers, in particular, can cause problems
    """
    if isinstance(input, dict):
        return OrderedDict(
            (_ascii_encode_dict(key), _ascii_encode_dict(input[key]))
            for key in sorted(input.keys()))
    elif isinstance(input, list):
        return [_ascii_encode_dict(element) for element in input]
    elif isinstance(input, unicode):
        return input.encode('ascii')
    else:
        return input


def _unicode_encode_dict(input):
    """
    Support method to ensure that JSON is converted to ascii since unicode
    identifiers, in particular, can cause problems
    """
    if isinstance(input, dict):
        return OrderedDict(
            (_unicode_encode_dict(key), _unicode_encode_dict(input[key]))
            for key in sorted(input.keys()))
    elif isinstance(input, list):
        return [_unicode_encode_dict(element) for element in input]
    elif isinstance(input, str):
        return unicode(input)
    else:
        return input
