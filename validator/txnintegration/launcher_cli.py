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
import json
import logging
import os
import pprint
import sys
import time
import traceback

from sawtooth.cli.exceptions import CliException
from sawtooth.cli.stats import run_stats
from sawtooth.exceptions import MessageException
from sawtooth.manage.node import NodeArguments
from sawtooth.manage.subproc import SubprocessNodeController
from sawtooth.manage.wrap import WrappedNodeController
from txnintegration.exceptions import ExitError
from txnintegration.utils import is_convergent
from txnintegration.utils import load_log_config
from txnintegration.utils import parse_configuration_file
from txnintegration.utils import Progress
from txnintegration.utils import TimeOut


logger = logging.getLogger(__name__)
pp = pprint.PrettyPrinter(indent=4)


def parse_args(args):
    parser = argparse.ArgumentParser()

    parser.add_argument('--config',
                        help='Base validator config file',
                        default=None)
    parser.add_argument('--count',
                        help='Number of validators to launch',
                        default=1,
                        type=int)
    parser.add_argument('--data-dir',
                        help='Where to store the logs, data, etc for the '
                             'network.  If omitted, a temp directory will be'
                             'used, and discarded on exit.',
                        default=None)
    parser.add_argument('--log-config',
                        help='The python logging config file to be passed '
                             'to the validators.',
                        default=None)
    parser.add_argument('--port',
                        help='The base gossip UDP port to use',
                        default=5500)
    parser.add_argument('--http-port',
                        help='The base HTTP port to use',
                        default=8800)

    return parser.parse_args(args)


def configure(args):
    opts = parse_args(args)

    validator_config = {}
    if opts.config is not None:
        if os.path.exists(opts.config):
            validator_config = parse_configuration_file(opts.config)
        else:
            raise ExitError("Config file does not exist: {}".format(
                opts.config))

    opts.log_config_dict = None
    if opts.log_config is not None:
        if not os.path.exists(opts.log_config):
            raise ExitError("log-config file does not exist: {}"
                            .format(opts.log_config))
        else:
            opts.log_config_dict = load_log_config(opts.log_config)

    keys = [
        'NodeName',
        'Listen',
        'KeyFile',
        'AdministrationNode',
        'DataDirectory',
        'LedgerURL',
    ]
    if any(k in validator_config for k in keys):
        print("Overriding the following keys from validator configuration "
              "file: {}".format(opts.config))
        for k in keys:
            if k in validator_config:
                print("\t{}".format(k))
                del validator_config[k]
    if opts.log_config:
        print("\tLogConfigFile")

    opts.validator_config = validator_config

    opts.count = max(1, opts.count)

    print("Configuration:")
    pp.pprint(opts.__dict__)

    return vars(opts)


def _poll_for_convergence(urls):
    to = TimeOut(256)
    convergent = False
    task_str = 'checking for minimal convergence on: {}'.format(urls)
    with Progress(task_str) as p:
        while convergent is False:
            try:
                convergent = is_convergent(urls, standard=2, tolerance=0)
            except MessageException:
                if to.is_timed_out():
                    raise CliException('timed out {}'.format(task_str))
                else:
                    p.step()
                    time.sleep(4)


def main():
    node_ctrl = None
    try:
        opts = configure(sys.argv[1:])
    except Exception as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    try:
        count = opts['count']

        # log_config = NEED
        currency_home = opts['data_dir']
        http_port = int(opts['http_port'])
        gossip_port = int(opts['port'])
        try:
            ledger_type = opts["validator_config"]["LedgerType"]
        except KeyError:
            # None defaults to poet0
            ledger_type = None
        node_ctrl = WrappedNodeController(SubprocessNodeController(),
                                          data_dir=currency_home)
        nodes = []
        for idx in range(count):
            node = NodeArguments("validator-{:0>3}".format(idx),
                                 http_port=http_port + idx,
                                 gossip_port=gossip_port + idx,
                                 ledger_type=ledger_type)
            nodes.append(node)
        currency_home = node_ctrl.get_data_dir()
        if opts['log_config_dict']:
            file_name = 'launcher_cli_global_log_config.js'
            full_name = '{}/etc/{}'.format(currency_home, file_name)
            with open(full_name, 'w') as f:
                f.write(json.dumps(opts['log_config_dict'], indent=4))
            opts['validator_config']['LogConfigFile'] = full_name
        if opts['validator_config']:
            file_name = 'launcher_cli_global_validator_config.js'
            with open('{}/etc/{}'.format(currency_home, file_name), 'w') as f:
                f.write(json.dumps(opts['validator_config'], indent=4))
            for nd in nodes:
                nd.config_files.append(file_name)
        # set up our urls (external interface)
        urls = ['http://localhost:%s' % x.http_port for x in nodes]
        # Make genesis block
        print('creating genesis block...')
        nodes[0].genesis = True
        node_ctrl.create_genesis_block(nodes[0])
        # Launch network (node zero will trigger bootstrapping)
        batch_size = 8
        print('staged-launching network (batch_size: {})...'
              .format(batch_size))
        lower_bound = 0
        while lower_bound < count:
            upper_bound = lower_bound + min(count - lower_bound, batch_size)
            for idx in range(lower_bound, upper_bound):
                print("launching {}".format(nodes[idx].node_name))
                node_ctrl.start(nodes[idx])
            _poll_for_convergence(urls[lower_bound:upper_bound])
            lower_bound = upper_bound
        run_stats(urls[0])
    except KeyboardInterrupt:
        print("\nExiting")
    except ExitError as e:
        # this is an expected error/exit, don't print stack trace -
        # the code raising this exception is expected to have printed the error
        # details
        print("\nFailed!\nExiting: {}".format(e))
    except:
        traceback.print_exc()
        print("\nFailed!\nExiting: {}".format(sys.exc_info()[0]))

    finally:
        if node_ctrl is not None:
            # stop all nodes
            for node_name in node_ctrl.get_node_names():
                node_ctrl.stop(node_name)
            with Progress("terminating network") as p:
                to = TimeOut(16)
                while len(node_ctrl.get_node_names()) > 0:
                    if to.is_timed_out():
                        break
                    time.sleep(1)
                    p.step()
            # force kill anything left over
            for node_name in node_ctrl.get_node_names():
                print("%s still 'up'; sending kill..." % node_name)
                node_ctrl.kill(node_name)
            node_ctrl.archive('launcher')
            node_ctrl.clean()


if __name__ == "__main__":
    main()
