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
import getpass
import os

from sawtooth_private_utxo.client import PrivateUtxoClient


def get_user(args):
    if args.user:
        user = args.user
    else:
        user = getpass.getuser()
    return user


def get_config_file_name(args, home=None):
    home = os.path.expanduser("~")

    return os.path.join(
        home, ".sawtooth",
        "private_utxo_{}.cfg".format(get_user(args)))


def get_key_dir():
    home = os.path.expanduser("~")
    return os.path.join(home, ".sawtooth", "keys")


def create_client(config):
    url = config.get('DEFAULT', 'url')
    key_file = config.get('DEFAULT', 'key_file')
    return PrivateUtxoClient(url, key_file)
