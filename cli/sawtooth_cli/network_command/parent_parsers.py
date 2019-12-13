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

from argparse import ArgumentParser
from sawtooth_cli.rest_client import RestClient


def make_rest_apis(urls, users):
    clients = []
    for i, url in enumerate(urls):
        try:
            user = users[i]
        except IndexError:
            user = ''
        clients.append(RestClient(url, user))
    return clients


def split_comma_append_args(arg_list):
    new_arg_list = []
    if not arg_list:
        return new_arg_list

    for arg in arg_list:
        new_arg_list.extend([x.strip() for x in arg.split(',')])

    return new_arg_list


def base_multinode_parser():
    """Creates a parser with arguments specific to sending HTTP requests
    to multiple REST APIs.

    Returns:
        {ArgumentParser}: Base parser with default HTTP args
    """
    base_parser = ArgumentParser(add_help=False)

    base_parser.add_argument(
        'urls',
        type=str,
        nargs='+',
        help="The URLs of the validator's REST APIs of interest, separated by"
        " commas or spaces. (no default)")
    base_parser.add_argument(
        '--users',
        type=str,
        action='append',
        metavar='USERNAME[:PASSWORD]',
        help='Specify the users to authorize requests, in the same order as '
        'the URLs, separate by commas. Passing empty strings between commas '
        'is supported.')

    return base_parser
