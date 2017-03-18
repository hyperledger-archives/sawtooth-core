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

from abc import ABCMeta
from abc import abstractmethod


class SgxStruct(metaclass=ABCMeta):
    """SgxStruct defines the base class that all Sgx* structures must
    implement
    """

    @abstractmethod
    def serialize_to_bytes(self):
        """Serializes a object representing an SGX structure to bytes
        laid out in its corresponding C/C++ format.

        NOTE: All integer struct fields are serialized to little endian
            format

        Returns:
            bytes: The C/C++ representation of the object as a struct
        """
        pass

    @abstractmethod
    def parse_from_bytes(self, raw_buffer):
        """Parses a byte array and creates the Sgx* object corresponding
        to the C/C++ struct.

        NOTE: All integer struct fields are parsed as little endian
            format

        Args:
            raw_buffer (bytes): A byte array representing the corresponding
                C/C++ struct used to parse into the object

        Returns:
            None

        Raises:
            TypeError: raw_buffer is not a byte array (aka, bytes)
            ValueError: raw_buffer is not a valid C/C++ struct layout
        """
        pass
