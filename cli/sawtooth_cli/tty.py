# Copyright 2017 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the 'License');
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

import sys
import os


DEFAULT_HEIGHT = 45
DEFAULT_WIDTH = 158


def size():
    """Determines the height and width of the console window

        Returns:
            tuple of int: The height in lines, then width in characters
    """
    try:
        assert os != 'nt' and sys.stdout.isatty()
        rows, columns = os.popen('stty size', 'r').read().split()
    except (AssertionError, AttributeError, ValueError):
        # in case of failure, use dimensions of a full screen 13" laptop
        rows, columns = DEFAULT_HEIGHT, DEFAULT_WIDTH

    return int(rows), int(columns)


def height():
    """Determines the height of console window in lines

        Returns:
            int: The height in lines
    """
    console_height, _ = size()
    return console_height


def width():
    """Determines the width of console window in characters

        Returns:
            int: The width in characters
    """
    _, console_width = size()
    return console_width
