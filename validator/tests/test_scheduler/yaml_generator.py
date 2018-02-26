# Copyright 2018 Intel Corporation
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

import argparse
import os
import random
import sys

import yaml


TEST_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.join(TEST_DIR, 'data')


def parse_args(args):
    parser = argparse.ArgumentParser()

    parser.add_argument(
        'file',
        help="The filepath and name relative to "
             "validator/tests/test_scheduler/data")

    parser.add_argument(
        '-s',
        '--seed',
        help="The seed to make the random generator reproduceable")

    parser.add_argument(
        '-a',
        '--addresses',
        default=100,
        help="The number of addresses in total")

    parser.add_argument(
        '--namespace',
        default='aaaaaa,.5',
        help="A namespace, float comma separated pair specifying "
             "a namespace to use for some portion of the addresses"
    )

    parser.add_argument(
        '-w',
        '--wildcard',
        default='70,70,70,70',
        help="A comma separated quad specifying min and max length for inputs "
             "then outputs")

    parser.add_argument(
        '-t',
        '--transactions',
        default="1,1",
        help="A comma separated pair of numbers for min and max transactions "
             "per batch")

    parser.add_argument(
        '-b',
        '--batches',
        default=100,
        help="The number of batches to produce")

    parser.add_argument(
        '-v',
        '--validity',
        default=1.0,
        type=float,
        help="A number between 0 and 1 specifying the probability of invalid "
             "transactions")

    parser.add_argument(
        '-i',
        '--inputs',
        default='2,3',
        help="A comma separated pair specifying the minimum and "
             "maximum number of addresses for inputs")

    parser.add_argument(
        '-o',
        '--outputs',
        default='2,3',
        help="A comma separated pair specifying the minimum "
             "and maximum number of addresses for outputs")

    return parser.parse_args(args)


class GeneratorCliException(Exception):
    pass


def main_wrapper(args):
    try:
        main(args)
    except GeneratorCliException as e:
        print(e)


def main(args):
    opts = parse_args(args=args)

    if opts.seed is None:
        seed = random.randrange(sys.maxsize)
    else:
        seed = int(opts.seed)
    random.seed(seed)

    cmd_header = generate_cmd_header(opts, seed=seed)

    parts = opts.transactions.split(',')
    if len(parts) != 2:
        raise GeneratorCliException(
            "-t, --transactions requires a comma separated pair")

    txn_min, txn_max = int(parts[0]), int(parts[1])

    charact = opts.namespace.split(',')
    if len(charact) != 2:
        raise GeneratorCliException(
            "-c, --characteristic requires a comma separated pair")
    namespace, portion = charact[0], float(charact[1])

    i_parts = opts.inputs.split(',')

    if len(i_parts) != 2:
        raise GeneratorCliException(
            '-i, --inputs requires a comma separated pair')

    min_inputs, max_inputs = int(i_parts[0]), int(i_parts[1])

    o_parts = opts.outputs.split(',')

    if len(o_parts) != 2:
        raise GeneratorCliException(
            '-o, --outputs requires a comma separated pair')

    min_outputs, max_outputs = int(o_parts[0]), int(o_parts[1])

    w_parts = opts.wildcard.split(',')
    if len(w_parts) != 4:
        raise GeneratorCliException(
            "-w, --wildcard requires a comma separated quad")

    min_input_length = max(0, int(w_parts[0]))
    max_input_length = min(70, int(w_parts[1]))
    min_output_length = max(0, int(w_parts[2]))
    max_output_length = min(70, int(w_parts[3]))

    if opts.file is None:
        raise GeneratorCliException(
            "The file name and path relative to the data directory is "
            "required")

    generate_yaml(os.path.join(DATA_DIR, opts.file),
                  cmd_header,
                  int(opts.addresses),
                  namespace,
                  min_input_length,
                  max_input_length,
                  min_output_length,
                  max_output_length,
                  portion,
                  min_inputs,
                  max_inputs,
                  min_outputs,
                  max_outputs,
                  txn_min,
                  txn_max,
                  int(opts.batches),
                  float(opts.validity))


def generate_yaml(filename,
                  cmd_header,
                  num_addresses,
                  namespace,
                  min_input_length,
                  max_input_length,
                  min_output_length,
                  max_output_length,
                  portion,
                  min_inputs,
                  max_inputs,
                  min_outputs,
                  max_outputs,
                  min_txns,
                  max_txns,
                  num_batches,
                  validity):
    namespaces = [namespace] * int(portion * num_addresses) +\
                 [''] * int((1.0 - portion) * num_addresses)
    addresses = list(map(generate_address, namespaces))

    if not os.path.exists(os.path.dirname(filename)):
        os.makedirs(os.path.dirname(filename))

    with open(filename, 'w') as outfile:
        outfile.writelines([
            "#\n",
            "#\n",
            "# Do not edit this file as it is machine generated. It "
            "can be reproduced with the following command.\n",
            cmd_header,
            "#\n",
            "#\n"
        ])
        outfile.write(
            yaml.dump(
                [generate_batch(addresses,
                                min_input_length,
                                max_input_length,
                                min_output_length,
                                max_output_length,
                                validity,
                                min_inputs,
                                max_inputs,
                                min_outputs,
                                max_outputs,
                                min_txns,
                                max_txns)
                 for _ in range(num_batches)],
                default_flow_style=False))


def generate_address(namespace):
    return namespace + "".join(
        [
            random.choice('abcdef0123456789')
            for _ in range(70 - len(namespace))
        ])


def generate_txn(addresses,
                 min_input_length,
                 max_input_length,
                 min_output_length,
                 max_output_length,
                 min_inputs,
                 max_inputs,
                 min_outputs,
                 max_outputs,
                 validity=True):
    inputs = [
        random.choice(addresses)
        for _ in range(random.randint(min_inputs, max_inputs))]
    inputs = list(
        map(
            lambda a: a[:generate_random_even_num(
                min_input_length,
                max_input_length)], inputs))
    outputs = [
        random.choice(addresses)
        for _ in range(random.randint(min_outputs, max_outputs))]
    addresses_to_set = [{a: None} for a in outputs]
    outputs = list(
        map(
            lambda a: a[:generate_random_even_num(
                min_output_length,
                max_output_length)],
            outputs))
    return {'inputs': inputs,
            'outputs': outputs,
            'addresses_to_set': addresses_to_set,
            'valid': validity}


def generate_batch(addresses,
                   min_input_length,
                   max_input_length,
                   min_output_length,
                   max_output_length,
                   validity,
                   min_inputs,
                   max_inputs,
                   min_outputs,
                   max_outputs,
                   min_txns,
                   max_txns):
    return [
        generate_txn(addresses,
                     min_input_length,
                     max_input_length,
                     min_output_length,
                     max_output_length,
                     min_inputs,
                     max_inputs,
                     min_outputs,
                     max_outputs,
                     random.random() < validity)
        for _ in range(random.randint(min_txns, max_txns))
    ]


def generate_random_even_num(min_num, max_num):
    """Generates a random even integer between min_num and max_num

    Args:
        min_num (int): The minimum the number can be.
        max_num (int): The maximum the number can be.

    Returns:
        (int): an even number.
    """

    num = random.randint(min_num, max_num)
    if num % 2 == 0:
        return num
    return num + 1


def generate_cmd_header(opts, seed):
    return "# gen-scheduler-test --seed {} -a {} --namespace {} " \
           "-w {} -t {} -b {} -v {} " \
           "-i {} -o {} <filename>\n".format(seed,
                                             opts.addresses,
                                             opts.namespace,
                                             opts.wildcard,
                                             opts.transactions,
                                             opts.batches,
                                             opts.validity,
                                             opts.inputs,
                                             opts.outputs)
