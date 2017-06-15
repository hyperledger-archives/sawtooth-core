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

from __future__ import print_function

import argparse
from argparse import Namespace
import logging
import os
import subprocess
import time
import yaml

from sawtooth_cli.exceptions import CliException
from sawtooth_manage.exceptions import ManagementError

from sawtooth_manage.node import NodeArguments
from sawtooth_manage.simple import SimpleNodeCommandGenerator
from sawtooth_manage.vnm import ValidatorNetworkManager

from sawtooth_manage.docker import DockerNodeController
from sawtooth_manage.subproc import SubprocessNodeController


LOGGER = logging.getLogger(__name__)


MANAGE_TYPES = 'docker', 'subprocess'

DEFAULT_MANAGE = 'docker'


def add_cluster_parser(subparsers, parent_parser):
    parser = subparsers.add_parser('cluster', parents=[parent_parser])

    cluster_subparsers = parser.add_subparsers(
        title='subcommands',
        dest='cluster_command')
    cluster_subparsers.required = True
    add_cluster_start_parser(cluster_subparsers, parent_parser)
    add_cluster_status_parser(cluster_subparsers, parent_parser)
    add_cluster_stop_parser(cluster_subparsers, parent_parser)
    add_cluster_extend_parser(cluster_subparsers, parent_parser)
    add_cluster_logs_parser(cluster_subparsers, parent_parser)


def add_cluster_status_parser(subparsers, parent_parser):
    parser = subparsers.add_parser('status', parents=[parent_parser])

    parser.add_argument(
        'node_names',
        metavar='NODE_NAME',
        help='report status of specific node(s)',
        nargs='*')


def add_cluster_start_parser(subparsers, parent_parser):

    epilog = '''details:
    The available transaction processors specified by -P depend upon the
    method (specified by -m). When using docker, the included processors
    can be found using the command 'docker images'.
    '''

    parser = subparsers.add_parser(
        'start', parents=[parent_parser],
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument(
        '--count',
        help='number of nodes to start',
        type=int,
        default=10)

    parser.add_argument(
        '-m', '--manage',
        help='style of validator management',
        choices=MANAGE_TYPES,
        default=DEFAULT_MANAGE)

    parser.add_argument(
        '--processors',
        '-P',
        help='the transaction processors that are part of node,'
             'e.g. tp_intkey_python, tp_intkey_java',
        nargs='*')


def add_cluster_stop_parser(subparsers, parent_parser):
    parser = subparsers.add_parser('stop', parents=[parent_parser])

    parser.add_argument(
        'node_names',
        metavar='NODE_NAME',
        help='stop specific node(s)',
        nargs='*')


def add_cluster_extend_parser(subparsers, parent_parser):
    parser = subparsers.add_parser('extend', parents=[parent_parser])

    parser.add_argument(
        '--count',
        help='number of nodes to add to network',
        type=int,
        default=1)


def add_cluster_logs_parser(subparsers, parent_parser):
    parser = subparsers.add_parser('logs', parents=[parent_parser])

    parser.add_argument(
        'node_names',
        metavar='NODE_NAME',
        help='get logs from specific validator nodes. implemented for '
             'docker',
        nargs='+')


def do_cluster(args):

    if args.cluster_command == 'start':
        do_cluster_start(args)
    elif args.cluster_command == 'status':
        do_cluster_status(args)
    elif args.cluster_command == 'stop':
        do_cluster_stop(args)
    elif args.cluster_command == 'extend':
        do_cluster_extend(args)
    elif args.cluster_command == 'logs':
        do_cluster_logs(args)
    else:
        raise AssertionError("invalid cluster command: {}".format(
            args.cluster_command))


def get_state_dir_name():
    home = os.path.expanduser("~")
    dir_name = os.path.join(home, '.sawtooth', 'cluster')
    return dir_name


def get_state_file_name():
    dir_name = get_state_dir_name()
    file_name = os.path.join(dir_name, 'state.yaml')
    return file_name


def load_state(start=False):
    file_name = get_state_file_name()
    if os.path.isfile(file_name):
        with open(file_name, 'r') as state_file:
            state = yaml.safe_load(state_file)
            return state
    elif start is True:
        dir_name = get_state_dir_name()
        # Ensure state directory exists
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)
        state = {
            'DesiredState': 'Stopped',
        }
        # Ensure state file exists
        save_state(state)
        return state
    else:
        raise CliException("Missing state file")


def save_state(state):
    file_name = get_state_file_name()
    with open(file_name, 'w') as state_file:
        yaml.dump(state, state_file, default_flow_style=False)


def get_node_controller(state, args):
    # Get base controller:
    manage_type = state['Manage']

    node_controller_types = {
        'docker': DockerNodeController,
        'subprocess': SubprocessNodeController
    }

    try:
        node_controller_type = node_controller_types[manage_type]
    except:
        # manage_type hasn't been added to node_controller_types
        if manage_type in MANAGE_TYPES:
            error_msg = '{} manamgement type not implemented'
        else:
            error_msg = 'Invalid management type: {}'
        raise CliException(error_msg.format(manage_type))

    node_controller = node_controller_type()

    # Return out construction:
    return node_controller


def do_cluster_start(args):
    state = load_state(start=True)

    manage_type = DEFAULT_MANAGE if args.manage is None else args.manage

    if "Manage" not in state or state["DesiredState"] == "Stopped":
        state['Manage'] = manage_type
    elif args.manage is not None and state['Manage'] != args.manage\
            and state["DesiredState"] == "Running":
        raise CliException('Cannot use two different Manage types.'
                           ' Already running {}'.format(state["Manage"]))

    state["DesiredState"] = "Running"

    if args.processors is None:
        raise CliException("Use -P to specify one or more processors")

    state['Processors'] = args.processors

    node_controller = get_node_controller(state, args)
    node_command_generator = SimpleNodeCommandGenerator()
    vnm = ValidatorNetworkManager(
        node_controller=node_controller,
        node_command_generator=node_command_generator)

    try:
        existing_nodes = vnm.get_node_names()
    except ManagementError as e:
        raise CliException(str(e))

    # Check for runnings nodes. If found, raise exception with message to use
    # sawtooth cluster extend command to add nodes to running network.
    for i in range(0, args.count):
        node_name = "validator-{:0>3}".format(i)
        if node_name in existing_nodes and vnm.is_running(node_name):
            print("Already running: {}".format(node_name))
            raise CliException("Please use 'sawtooth cluster extend'\
             to add more nodes.")

    for i in range(0, args.count):
        node_name = "validator-{:0>3}".format(i)
        if node_name in existing_nodes and vnm.is_running(node_name):
            print("Already running: {}".format(node_name))
            continue

        # genesis is true for the first node
        genesis = (i == 0)
        gossip_port = 5500 + i
        http_port = 8800 + i

        node_args = NodeArguments(node_name, http_port=http_port,
                                  gossip_port=gossip_port, genesis=genesis)

        if node_args.genesis is True:
            node_controller.create_genesis_block(node_args)

        node_command_generator.start(node_args)

    save_state(state)

    print('Starting validators')

    try:
        vnm.update()
    except ManagementError as e:
        raise CliException(str(e))

    subprocess_manage = 'subprocess', 'subprocess-legacy'
    if state["Manage"] in subprocess_manage:
        print('Validators ready')
        try:
            while True:
                time.sleep(128)
        except KeyboardInterrupt:
            print()
            node_names = vnm.get_node_names()
            ns = Namespace(cluster_command='stop', command='cluster',
                           node_names=node_names, verbose=None)
            do_cluster_stop(ns)


def do_cluster_stop(args):
    state = load_state()

    node_controller = get_node_controller(state, args)
    node_command_generator = SimpleNodeCommandGenerator()
    vnm = ValidatorNetworkManager(
        node_controller=node_controller,
        node_command_generator=node_command_generator)

    if args.node_names:
        node_names = args.node_names
    else:
        node_names = vnm.get_node_names()

    # if node_names is empty, stop doesn't get called
    for node_name in node_names:

        node_command_generator.stop(node_name)

    state["DesiredState"] = "Stopped"

    save_state(state)

    print('Stopping validators')

    vnm.update()

    # Wait up to 16 seconds for our targeted nodes to gracefully shut down
    def find_still_up(targeted_nodes):
        return set(vnm.get_node_names()).intersection(set(targeted_nodes))

    timeout = 16
    mark = time.time()
    while find_still_up(node_names):
        if time.time() - mark > timeout:
            break
        time.sleep(1)

    # Force kill any targeted nodes that are still up
    for node_name in find_still_up(node_names):
        print("Node name still up: killing {}".format(node_name))
        node_controller.kill(node_name)


def do_cluster_status(args):
    state = load_state()

    node_controller = get_node_controller(state, args)
    node_command_generator = SimpleNodeCommandGenerator()
    vnm = ValidatorNetworkManager(
        node_controller=node_controller,
        node_command_generator=node_command_generator)

    if args.node_names:
        node_names = args.node_names
        node_superset = vnm.get_node_names()
        for node_name in args.node_names:
            try:
                node_name in node_superset
            except KeyError:
                raise CliException(
                    "{} is not a known node name".format(node_name))
    else:
        node_names = vnm.get_node_names()

    # Check expected status of nodes vs what is returned from vnm
    print("NodeName".ljust(15), "Status".ljust(10))
    for node_name in node_names:
        status = vnm.status(node_name)
        if status == "UNKNOWN":
            status = "Not Running"
        print(node_name.ljust(15), status.ljust(10))


def do_cluster_extend(args):
    state = load_state()

    node_controller = get_node_controller(state, args)
    node_command_generator = SimpleNodeCommandGenerator()
    vnm = ValidatorNetworkManager(
        node_controller=node_controller,
        node_command_generator=node_command_generator)

    try:
        existing_nodes = vnm.get_node_names()
    except ManagementError as e:
        raise CliException(str(e))

    desired_stated = state["DesiredState"]

    if desired_stated != "Running":
        raise CliException(
            "You must have a running network.\n" +
            "Use the cluster start command to start a validator network.")

    print("Extending network by {} nodes.".format(args.count))

    index_offset = len(existing_nodes)

    for i in range(0, args.count):
        j = i + index_offset
        node_name = "validator-{:0>3}".format(j)

        if node_name in existing_nodes and vnm.is_running(node_name):
            print("Already running: {}".format(node_name))
            continue

        # genesis is true for the first node
        genesis = (j == 0)
        gossip_port = 5500 + j
        http_port = 8800 + j

        node_args = NodeArguments(node_name, http_port=http_port,
                                  gossip_port=gossip_port, genesis=genesis)
        node_command_generator.start(node_args)

    save_state(state)

    try:
        vnm.update()
    except ManagementError as e:
        raise CliException(str(e))


def do_cluster_logs(args):
    state = load_state()

    supported_types = ('docker',)
    if state['Manage'] in supported_types:
        prefix = 'sawtooth-cluster-0'

        for node_name in args.node_names:
            try:
                node_num = node_name[len('validator-'):]
                processes = state['Processors'] + ['validator']
                containers = ['-'.join([prefix, proc, node_num])
                              for proc in processes]

                for c in containers:
                    print("Logs for container: " + c + "of node: " + node_name)
                    cmd = ['docker', 'logs', c]
                    handle = subprocess.Popen(cmd)
                    while handle.returncode is None:
                        handle.poll()

            except subprocess.CalledProcessError as cpe:
                raise CliException(str(cpe))
    else:
        print("logs not implemented for {}".format(state['Manage']))
