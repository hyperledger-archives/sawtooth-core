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

import sawtooth_signing.secp256k1_signer as signing
from sawtooth_supplychain.common.exceptions import SupplyChainException


def add_init_parser(subparsers, parent_parser):
    parser = subparsers.add_parser('init', parents=[parent_parser])

    parser.add_argument(
        '--username',
        type=str,
        help='the name of the agent')

    parser.add_argument(
        '--url',
        type=str,
        help='the url of the REST API')


def save_config(config):
    home = os.path.expanduser("~")

    config_file = os.path.join(home, ".sawtooth", "supplychain.cfg")
    if not os.path.exists(os.path.dirname(config_file)):
        os.makedirs(os.path.dirname(config_file))

    with open("{}.new".format(config_file), "w") as fd:
        config.write(fd)
    if os.name == 'nt':
        if os.path.exists(config_file):
            os.remove(config_file)
    os.rename("{}.new".format(config_file), config_file)


def do_init(args, config):
    username = config.get('DEFAULT', 'username')
    if args.username is not None:
        username = args.username

    url = config.get('DEFAULT', 'url')
    if args.url is not None:
        url = args.url

    config.set('DEFAULT', 'username', username)
    print("set username: {}".format(username))
    config.set('DEFAULT', 'url', url)
    print("set url: {}".format(url))

    save_config(config)

    priv_filename = config.get('DEFAULT', 'key_file')
    if priv_filename.endswith(".priv"):
        addr_filename = priv_filename[0:-len(".priv")] + ".addr"
    else:
        addr_filename = priv_filename + ".addr"

    if not os.path.exists(priv_filename):
        try:
            if not os.path.exists(os.path.dirname(priv_filename)):
                os.makedirs(os.path.dirname(priv_filename))

            privkey = signing.generate_privkey()
            pubkey = signing.generate_pubkey(privkey)
            addr = signing.generate_identifier(pubkey)

            with open(priv_filename, "w") as priv_fd:
                print("writing file: {}".format(priv_filename))
                priv_fd.write(privkey)
                priv_fd.write("\n")

            with open(addr_filename, "w") as addr_fd:
                print("writing file: {}".format(addr_filename))
                addr_fd.write(addr)
                addr_fd.write("\n")
        except IOError as ioe:
            raise SupplyChainException("IOError: {}".format(str(ioe)))
