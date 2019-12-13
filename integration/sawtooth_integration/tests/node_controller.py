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
# --------------------------------------------------------------------------

import os
import subprocess
import shlex
import time
import logging
import signal

from sawtooth_integration.tests.integration_tools import wait_for_rest_apis


LOGGER = logging.getLogger(__name__)


# peering arrangements

def peer_with_genesis_only(num):
    if num > 0:
        return '--peers {}'.format(
            endpoint(0))

    return ''


def peer_to_preceding_only(num):
    if num > 0:
        return '--peers {}'.format(
            endpoint(num - 1))

    return ''


def everyone_peers_with_everyone(num):
    if num > 0:
        peers = ','.join(endpoint(i) for i in range(num))
        return '--peers {}'.format(peers)

    return ''


# processor arrangements
def intkey_config_identity(num):
    return (
        'intkey-tp-python',
        'settings-tp',
        'identity-tp',
    )


# scheduler arrangements

def all_serial(num):
    return 'serial'


def all_parallel(num):
    return 'parallel'


def even_parallel_odd_serial(num):
    return 'parallel' if num % 2 == 0 else 'serial'


def even_serial_odd_parallel(num):
    return 'parallel' if num % 2 == 1 else 'serial'


# node

def start_node(num,
               processor_func,
               peering_func,
               scheduler_func,
               sawtooth_home,
               validator_cmd_func):
    rest_api = start_rest_api(num)
    processors = start_processors(num, processor_func)
    engine = start_engine(num)
    validator = start_validator(num,
                                peering_func,
                                scheduler_func,
                                sawtooth_home,
                                validator_cmd_func)

    wait_for_rest_apis(['127.0.0.1:{}'.format(8008 + num)])

    return [rest_api] + processors + [engine] + [validator]


def stop_node(process_list):
    # This may seem a little dramatic, but seriously,
    # validators don't go down without a fight.
    for _ in range(2):
        for process in process_list:
            pid = process.pid
            LOGGER.debug('Stopping process %s', pid)
            process.send_signal(signal.SIGINT)
        time.sleep(15)


# validator

def validator_cmds(num,
                   peering_func,
                   scheduler_func,
                   sawtooth_home,
                   initial_wait_time=3000.0,
                   minimum_wait_time=1.0,
                   target_wait_time=20.0,
                   block_claim_delay=1,
                   key_block_claim_limit=25,
                   population_estimate_sample_size=50,
                   signup_commit_maximum_delay=0,
                   ztest_maximum_win_deviation=3.075,
                   ztest_minimum_win_count=3,
                   ):
    '''
    Return a list consisting of the commands
    needed to start the validator for the num-th node.

    If num == 0, the command will start the genesis validator.

    Args:
        num (int): the num-th node
        peering_func (int -> str): a function of one argument n
            returning a string specifying the peers of the num-th node
    '''
    keygen = 'sawadm keygen {}'.format(
        os.path.join(sawtooth_home, 'keys', 'validator'))

    validator = ' '.join([
        'sawtooth-validator -v',
        '--scheduler {}'.format(scheduler_func(num)),
        '--endpoint {}'.format(endpoint(num)),
        '--bind component:{}'.format(bind_component(num)),
        '--bind network:{}'.format(bind_network(num)),
        '--bind consensus:{}'.format(bind_consensus(num)),
        peering_func(num)])

    # genesis stuff
    priv = os.path.join(sawtooth_home, 'keys', 'validator.priv')

    config_genesis = ' '.join([
        'sawset genesis',
        '-k {}'.format(priv),
        '-o {}'.format(os.path.join(
            sawtooth_home, 'data', 'config-genesis.batch'))
    ])

    genesis = ' '.join([
        'sawadm genesis',
        os.path.join(sawtooth_home, 'data', 'config-genesis.batch')
    ])

    validator_cmd_list = (
        [keygen, validator] if num > 0
        else [
            keygen,
            config_genesis,
            genesis,
            validator,
        ]
    )

    return validator_cmd_list


def simple_validator_cmds(*args, **kwargs):
    """Used with SetSawtoothHome in integrationtools, to have more control
    at the test file level over how the validator is started.

    Returns:
        str : The validator startup command.
    """
    return ['sawtooth-validator -v']


def start_validator(num,
                    peering_func,
                    scheduler_func,
                    sawtooth_home,
                    validator_cmd_func):
    cmds = validator_cmd_func(num, peering_func, scheduler_func,
                              sawtooth_home)
    for cmd in cmds[:-1]:
        process = start_process(cmd)
        process.wait(timeout=60)
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, cmd)

    # only return the validator process (the rest are completed)
    return start_process(cmds[-1])


# transaction processors

def processor_cmds(num, processor_func):
    '''
    Return a list of the commands needed to start
    the transaction processors for the num-th node.

    Args:
        num (int): the num-th node
        processor_func (int -> tuple): a function of one argument n
            returning a tuple specifying the processors that should
            be started for the n-th node
    '''
    processors = processor_func(num)

    processor_cmd_list = [
        '{p} {v} -C {a}'.format(
            p=processor,
            v=(processor_verbosity(processor)),
            a=connection_address(num))
        for processor in processors
    ]

    return processor_cmd_list


def processor_verbosity(processor_name):
    '''
    Transactions processors like intkey and xo are very talkative,
    so start them with minimal verbosity. Other TPs can be started
    with -v or even -vv if so desired.
    '''
    acceptably_quiet = 'config', 'registry'

    for keyword in acceptably_quiet:
        if keyword in processor_name:
            return '-v'

    return ''


def start_processors(num, processor_func):
    return [
        start_process(cmd)
        for cmd in processor_cmds(num, processor_func)
    ]


# consensus engine

def engine_cmd(num):
    return 'devmode-engine-rust --connect {s} {v}'.format(
        s=engine_connection_address(num),
        v='-v'
    )


def start_engine(num):
    return start_process(engine_cmd(num))


# rest_api
def rest_api_cmd(num):
    return 'sawtooth-rest-api --connect {s} --bind 127.0.0.1:{p}'.format(
        s=connection_address(num),
        p=(8008 + num)
    )


def start_rest_api(num):
    return start_process(
        rest_api_cmd(num))


# addresses
def endpoint(num):
    return 'tcp://127.0.0.1:{}'.format(8800 + num)


def connection_address(num):
    return 'tcp://127.0.0.1:{}'.format(4004 + num)


def engine_connection_address(num):
    return 'tcp://127.0.0.1:{}'.format(5050 + num)


def http_address(num):
    return 'http://127.0.0.1:{}'.format(8008 + num)


def bind_component(num):
    return 'tcp://127.0.0.1:{}'.format(4004 + num)


def bind_network(num):
    return 'tcp://127.0.0.1:{}'.format(8800 + num)


def bind_consensus(num):
    return 'tcp://127.0.0.1:{}'.format(5050 + num)


# execution

def start_process(cmd):
    LOGGER.debug('Running command %s', cmd)
    return subprocess.Popen(
        shlex.split(cmd))
