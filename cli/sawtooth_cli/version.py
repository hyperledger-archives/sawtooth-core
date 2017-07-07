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

from sawtooth_cli.rest_client import RestClient
from sawtooth_cli.parent_parsers import base_http_parser


def add_version_parser(subparsers, parent_parser):
    """Adds arguments parsers for the version command

        Args:
            subparsers: Add parsers to this subparser object
            parent_parser: The parent argparse.ArgumentParser object
    """
    subparsers.add_parser('version', parents=[base_http_parser()])


def do_version(args):
    """Print the version information for the sawtooth

        Args:
            args: The parsed arguments sent to the command at runtime
    """
    rest_client = RestClient(args.url, args.user)
    version = rest_client.get_version()
    print("sawtooth version {}".format(version))
