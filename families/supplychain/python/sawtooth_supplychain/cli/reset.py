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


def add_reset_parser(subparsers, parent_parser):
    subparsers.add_parser('reset', parents=[parent_parser])


def do_reset(args, config):
    home = os.path.expanduser("~")

    config_file = os.path.join(home, ".sawtooth", "supplychain.cfg")
    if os.path.exists(config_file):
        os.remove(config_file)
        print('Removed {}'.format(config_file))

    priv_filename = config.get('DEFAULT', 'key_file')
    if priv_filename.endswith(".priv"):
        addr_filename = priv_filename[0:-len(".priv")] + ".addr"
    else:
        addr_filename = priv_filename + ".addr"

    if os.path.exists(priv_filename):
        os.remove(priv_filename)
        print('Removed {}'.format(priv_filename))

    if os.path.exists(addr_filename):
        os.remove(addr_filename)
        print('Removed {}'.format(addr_filename))
