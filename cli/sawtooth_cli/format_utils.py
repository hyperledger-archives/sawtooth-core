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

import itertools
import sys
import csv
import json
import yaml

from sawtooth_cli import tty
from sawtooth_cli.exceptions import CliException


def format_terminal_row(headers, example_row):
    """Uses headers and a row of example data to generate a format string
    for printing a single row of data.

    Args:
        headers (tuple of strings): The headers for each column of data
        example_row (tuple): A representative tuple of strings or ints

    Returns
        string: A format string with a size for each column
    """

    def format_column(col):
        if isinstance(col, str):
            return '{{:{w}.{w}}}'
        return '{{:<{w}}}'

    widths = [max(len(h), len(str(d))) for h, d in zip(headers, example_row)]

    # Truncate last column to fit terminal width
    original_last_width = widths[-1]
    if sys.stdout.isatty():
        widths[-1] = max(
            len(headers[-1]),
            # console width - width of other columns and gutters - 3 for '...'
            tty.width() - sum(w + 2 for w in widths[0:-1]) - 3)

    # Build format string
    cols = [format_column(c).format(w=w) for c, w in zip(example_row, widths)]
    format_string = '  '.join(cols)
    if original_last_width > widths[-1]:
        format_string += '...'

    return format_string


def print_terminal_table(headers, data_list, parse_row_fn):
    """Uses a set of headers, raw data, and a row parsing function, to print
    data to the terminal in a table of rows and columns.

    Args:
        headers (tuple of strings): The headers for each column of data
        data_list (list of dicts): Raw response data from the validator
        parse_row_fn (function): Parses a dict of data into a tuple of columns
            Expected args:
                data (dict): A single response object from the validator
            Expected return:
                cols (tuple): The properties to display in each column
    """
    data_iter = iter(data_list)
    try:
        example = next(data_iter)
        example_row = parse_row_fn(example)
        data_iter = itertools.chain([example], data_iter)
    except StopIteration:
        example_row = [''] * len(headers)

    format_string = format_terminal_row(headers, example_row)

    top_row = format_string.format(*headers)
    print(top_row[0:-3] if top_row.endswith('...') else top_row)
    for data in data_iter:
        print(format_string.format(*parse_row_fn(data)))


def print_csv(headers, data_list, parse_row_fn):
    """Takes headers, data, and a row parsing function, and prints data
    to the console in a csv format.
    """
    try:
        writer = csv.writer(sys.stdout)
        writer.writerow(headers)
        for data in data_list:
            writer.writerow(parse_row_fn(data))
    except csv.Error as e:
        raise CliException('Error writing CSV: {}'.format(e))


def print_json(data):
    """Takes any JSON serializable data and prints it to the console.
    """
    print(json.dumps(
        data,
        indent=2,
        separators=(',', ': '),
        sort_keys=True))


def print_yaml(data):
    """Takes any YAML serializable data and prints it to the console.
    """
    print(yaml.dump(data, default_flow_style=False)[0:-1])
