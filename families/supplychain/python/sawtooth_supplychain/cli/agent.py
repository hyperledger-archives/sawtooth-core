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
from sawtooth_supplychain.cli.common import create_client
from sawtooth_supplychain.common.exceptions import SupplyChainException


def add_agent_parser(subparsers, parent_parser):
    parser = subparsers.add_parser('agent', parents=[parent_parser])
    agent_subparsers = parser.add_subparsers(
        title='subcommands', dest='agent_command')

    add_agent_create_parser(agent_subparsers)
    add_agent_list_parser(agent_subparsers)
    add_agent_show_parser(agent_subparsers)


def add_agent_create_parser(subparsers):
    parser = subparsers.add_parser('create')

    parser.add_argument(
        'name',
        type=str,
        help='The name of the new Agent')


def add_agent_list_parser(subparsers):
    subparsers.add_parser(
        'list',
        help='Show a list of all the Agents')


def add_agent_show_parser(subparsers):
    parser = subparsers.add_parser(
        'show',
        help='Show an Agent')

    parser.add_argument(
        'name',
        type=str,
        help='The identifier of the agent to show')


def do_agent(args, config):
    if args.agent_command == 'create':
        do_agent_create(args, config)
    elif args.agent_command == 'list':
        do_agent_list(args, config)
    elif args.agent_command == 'show':
        do_agent_show(args, config)
    else:
        raise SupplyChainException('invalid command: {}'.format(args.command))


def do_agent_create(args, config):
    name = args.name

    client = create_client(config)
    response = client.agent_create(name)
    print('Response: {}'.format(response))


def do_agent_list(args, config):
    client = create_client(config)
    agents = client.agent_list()

    if agents is not None:
        fmt = '{:64} {}'
        print('AGENTS')
        print(fmt.format('PUBLIC KEY', 'NAME'))
        for agent in agents:
            print(fmt.format(agent.identifier, agent.name))
    else:
        print('No Agents Found.')


def do_agent_show(args, config):
    name = args.name

    client = create_client(config)
    agent = client.agent_get(name)

    if agent is not None:
        fmt = '{:15}: {}'
        print('AGENT')
        print(fmt.format('PUBLIC KEY', agent.identifier))
        print(fmt.format('NAME', agent.name))

    else:
        print('Agent not found: {}'.format(name))
