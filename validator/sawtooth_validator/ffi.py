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

import ctypes
import logging
import os
import sys


LOGGER = logging.getLogger(__name__)


class Library:

    def __init__(self):
        lib_prefix_mapping = {
            "darwin": "lib",
            "linux": "lib",
            "linux2": "lib",
        }
        lib_suffix_mapping = {
            "darwin": ".dylib",
            "linux": ".so",
            "linux2": ".so",
        }

        os_name = sys.platform

        lib_location = os.environ.get('SAWTOOTH_LIB_HOME', '')
        if lib_location and lib_location[-1:] != '/':
            lib_location += '/'

        try:
            lib_prefix = lib_prefix_mapping[os_name]
            lib_suffix = lib_suffix_mapping[os_name]
        except KeyError:
            raise OSError("OS isn't supported: {}".format(os_name))

        library_path = "{}{}sawtooth_validator{}".format(
            lib_location, lib_prefix, lib_suffix)

        LOGGER.debug("loading library %s", library_path)

        self._cdll = ctypes.CDLL(library_path)

    def call(self, name, *args):
        return getattr(self._cdll, name)(*args)


LIBRARY = Library()


def prepare_byte_result():
    """Returns pair of byte pointer and size value for use as return parameters
    in a LIBRARY call
    """
    return (ctypes.POINTER(ctypes.c_uint8)(), ctypes.c_size_t(0))


def from_c_bytes(c_data, c_data_len):
    """Takes a byte pointer and a length and converts it into a python bytes
    value.
    """
    # pylint: disable=invalid-slice-index
    return bytes(c_data[:c_data_len.value])
