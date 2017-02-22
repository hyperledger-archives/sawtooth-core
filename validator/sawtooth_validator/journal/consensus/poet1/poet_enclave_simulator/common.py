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
from collections import OrderedDict

import cbor


def pretty_print_dict(dictionary):
    """Generates a pretty-print formatted version of the input JSON.

    Args:
        dictionary (str): the JSON string to format.

    Returns:
        str: pretty-print formatted string.
    """
    return json.dumps(ascii_encode_dict(dictionary), indent=2, sort_keys=True)


def json2dict(dictionary):
    """Deserializes JSON into a dictionary.

    Args:
        dictionary (str): the JSON string to deserialize.

    Returns:
        dict: a dictionary object reflecting the structure of the JSON.
    """
    return ascii_encode_dict(json.loads(dictionary))


def dict2json(dictionary):
    """Serializes a dictionary into JSON.

    Args:
        dictionary (dict): a dictionary object to serialize into JSON.

    Returns:
        str: a JSON string reflecting the structure of the input dict.
    """
    return json.dumps(ascii_encode_dict(dictionary))


def cbor2dict(dictionary):
    """Deserializes CBOR into a dictionary.

    Args:
        dictionary (bytes): the CBOR object to deserialize.

    Returns:
        dict: a dictionary object reflecting the structure of the CBOR.
    """

    return ascii_encode_dict(cbor.loads(dictionary))


def dict2cbor(dictionary):
    """Serializes a dictionary into CBOR.

    Args:
        dictionary (dict): a dictionary object to serialize into CBOR.

    Returns:
        bytes: a CBOR object reflecting the structure of the input dict.
    """

    return cbor.dumps(_unicode_encode_dict(dictionary), sort_keys=True)


def ascii_encode_dict(item):
    """
    Support method to ensure that JSON is converted to ascii since unicode
    identifiers, in particular, can cause problems
    """
    if isinstance(item, dict):
        return OrderedDict(
            (ascii_encode_dict(key), ascii_encode_dict(item[key]))
            for key in sorted(item.keys()))
    elif isinstance(item, list):
        return [ascii_encode_dict(element) for element in item]
    elif isinstance(item, str):
        return item
    else:
        return item


def _unicode_encode_dict(item):
    """
    Support method to ensure that JSON is converted to ascii since unicode
    identifiers, in particular, can cause problems
    """
    if isinstance(item, dict):
        return OrderedDict(
            (_unicode_encode_dict(key), _unicode_encode_dict(item[key]))
            for key in sorted(item.keys()))
    elif isinstance(item, list):
        return [_unicode_encode_dict(element) for element in item]
    elif isinstance(item, str):
        return str(item)
    else:
        return item
