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

import os
import sys


def ensure_directory(sawtooth_home_path, posix_fallback_path):
    """Ensures the one of the given sets of directories exists.

    The dirctory in sawtooth_home_path is ensured to exist, if `SAWTOOTH_HOME`
    exists. If the host operating system is windows, `SAWTOOTH_HOME` is
    defaulted to `C:\\Program Files (x86)\\Intel\\sawtooth-validator`,
    Otherwise, the given posix fallback path is ensured to exist.

    Args:
        sawtooth_home_dirs (str): Subdirectory of `SAWTOOTH_HOME`.
        posix_fallback_dir (str): Fallback directory path if `SAWTOOTH_HOME` is
            unset on posix host system.

    Returns:
        str: The path determined to exist.
    """
    if 'SAWTOOTH_HOME' in os.environ:
        sawtooth_home_dirs = sawtooth_home_path.split('/')
        sawtooth_dir = os.path.join(os.environ['SAWTOOTH_HOME'],
                                    *sawtooth_home_dirs)
    elif os.name == 'nt':
        default_win_home = \
            'C:\\Program Files (x86)\\Intel\\sawtooth-validator\\'
        sawtooth_home_dirs = sawtooth_home_path.split('/')
        sawtooth_dir = os.path.join(default_win_home, *sawtooth_home_dirs)
    else:
        sawtooth_dir = posix_fallback_path

    if not os.path.exists(sawtooth_dir):
        try:
            os.makedirs(sawtooth_dir, exist_ok=True)
        except OSError as e:
            print('Unable to create {}: {}'.format(sawtooth_dir, e),
                  file=sys.stderr)
            sys.exit(1)

    return sawtooth_dir
