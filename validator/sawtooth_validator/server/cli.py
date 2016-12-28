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

import sys
import argparse

from sawtooth_validator.server.core import Validator


def parse_args(args):
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument('--network-endpoint',
                        help='Network endpoint URL',
                        default='tcp://*:8800',
                        type=str)
    parser.add_argument('--component-endpoint',
                        help='Validator component service endpoint',
                        default='0.0.0.0:40000',
                        type=str)
    parser.add_argument('--peers',
                        help='A list of peers to attempt to connect to '
                             'in the format tcp://hostname:port',
                        nargs='+')

    return parser.parse_args(args)


def main(args=sys.argv[1:]):
    opts = parse_args(args)

    validator = Validator(opts.network_endpoint,
                          opts.component_endpoint,
                          opts.peers)

    try:
        validator.start()
    except KeyboardInterrupt:
        print(sys.stderr, "Interrupted!")
    finally:
        validator.stop()
