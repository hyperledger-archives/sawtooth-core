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
import os
import sys

from sawtooth_manage.exceptions import ManagementError


def find_txnvalidator():
    script_dir = os.path.dirname(os.path.realpath(__file__))

    search_path = []
    if "CURRENCYHOME" in os.environ:
        search_path.append(os.path.join(os.environ['CURRENCYHOME'], 'bin'))

    search_path.append(os.path.realpath(os.path.join(script_dir, '..', 'bin')))

    if 'PATH' in os.environ:
        search_path.extend(os.environ['PATH'].split(os.pathsep))

    for directory in search_path:
        for filename in ['txnvalidator', 'txnvalidator.exe']:
            if os.path.exists(os.path.join(directory, filename)):
                return os.path.join(directory, filename)

    return None


def get_executable_script(script_name):
    '''
    Searches PATH environmental variable to find the information needed to
    execute a script.
    Args:
        script_name:  the name of the 'executable' script
    Returns:
        ret_val (list<str>): A list containing the python executable, and the
        full path to the script.  Includes sys.executable, because certain
        operating systems cannot execute scripts directly.
    '''
    ret_val = None
    if 'PATH' not in os.environ:
        raise ManagementError('no PATH environmental variable')
    search_path = os.environ['PATH']
    for directory in search_path.split(os.pathsep):
        if os.path.exists(os.path.join(directory, script_name)):
            ret_val = os.path.join(directory, script_name)
            break
    if ret_val is not None:
        ret_val = [sys.executable, ret_val]
    else:
        raise ManagementError("could not locate %s" % (script_name))
    return ret_val
