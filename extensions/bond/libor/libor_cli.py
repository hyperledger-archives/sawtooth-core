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

import argparse
import logging
import ConfigParser
import getpass
import os
import traceback
import sys
import urllib2
import re
from datetime import datetime
from colorlog import ColoredFormatter
from bs4 import BeautifulSoup
import pybitcointools

from libor.libor_client import LIBORClient
from libor.libor_exceptions import LIBORClientException


def check_date(value):
    try:
        date = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError(
            'date {} is not in ISO-8601 format (YYYY-MM-DD)'.format(value))
    return date


def create_console_handler(verbose_level):
    clog = logging.StreamHandler()
    formatter = ColoredFormatter(
        "%(log_color)s[%(asctime)s %(levelname)-8s%(module)s]%(reset)s "
        "%(white)s%(message)s",
        datefmt="%H:%M:%S",
        reset=True,
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red',
        })

    clog.setFormatter(formatter)

    if verbose_level == 0:
        clog.setLevel(logging.WARN)
    elif verbose_level == 1:
        clog.setLevel(logging.INFO)
    else:
        clog.setLevel(logging.DEBUG)

    return clog


def setup_loggers(verbose_level):
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.addHandler(create_console_handler(verbose_level))


def add_submit_parser(subparsers, parent_parser):
    parser = subparsers.add_parser('submit', parents=[parent_parser])

    parser.add_argument(
        '--date',
        type=check_date,
        help='the date to retrieve and submit LIBOR rates for (no date '
             'means the most recent).  The date must be in ISO-8601 format '
             'YYYY-MM-DD.')
    parser.add_argument(
        '--keyfile',
        type=str,
        required=True,
        help='the key file that contains the key used to sign the LIBOR '
             'transaction and rates data (not the transaction itself)')
    parser.add_argument(
        '--url',
        type=str,
        help='the URL of the validator')
    parser.add_argument(
        '--wait',
        action='store_true',
        default=False,
        help='wait for this commit before exiting')


def add_list_parser(subparsers, parent_parser):
    parser = subparsers.add_parser('list', parents=[parent_parser])

    parser.add_argument(
        '--date',
        type=check_date,
        help='the date for which rates will be printed (no date '
             'means all known dates).  The date must be in ISO-8601 format '
             'YYYY-MM-DD.')
    parser.add_argument(
        '--url',
        type=str,
        help='the URL of the validator')


def create_parent_parser(prog_name):
    parser = argparse.ArgumentParser(prog=prog_name, add_help=False)
    parser.add_argument(
        '-v', '--verbose',
        action='count',
        help='enable more verbose output')

    return parser


def create_parser(prog_name):
    parent_parser = create_parent_parser(prog_name)

    parser = argparse.ArgumentParser(
        parents=[parent_parser],
        formatter_class=argparse.RawDescriptionHelpFormatter)

    subparsers = parser.add_subparsers(title='subcommands', dest='command')

    add_submit_parser(subparsers, parent_parser)
    add_list_parser(subparsers, parent_parser)

    return parser


def do_submit(args, config):
    # Try to read the LIBOR data from the WSJ web site, adding the date to the
    # URL if a specific date was requested
    try:
        url = urllib2.urlopen(
            'http://online.wsj.com/mdc/public/page/2_3020-libor{}.html'.format(
                args.date.strftime('-%Y%m%d') if args.date is not None else ''
            ))
    except urllib2.HTTPError as ex:
        raise LIBORClientException('Failed to read URL: {}'.format(ex))

    html = url.read()
    url.close()

    # Parse the HTML so that we can do the searching we want to do
    page = BeautifulSoup(html, 'html5lib')

    # Look for a div with class 'tableDesc' and parse its text element to see
    # if there is an effective date.  If not, there is no LIBOR data for us
    # to read.
    tag = page.select_one('div.tableDesc')
    if tag is not None:
        match = re.match(r'.*effective.*(\d+/\d+/\d+).*', tag.text)
    if tag is None or match is None:
        raise LIBORClientException(
            'There appears to be no LIBOR data for the date requested')

    # We need to parse the mm/dd/yyyy format into a date object so we can use
    # it later in our request to submit the rates
    date = datetime.strptime(match.group(1), '%m/%d/%Y').date()
    rates = {}
    maturity_mapping = {
        'Overnight': 'Overnight',
        '1 Week': 'OneWeek',
        '1 Month': 'OneMonth',
        '2 Month': 'TwoMonth',
        '3 Month': 'ThreeMonth',
        '6 Month': 'SixMonth',
        '1 Year': 'OneYear',
    }

    # Now we need to find nodes with a class of 'text'.
    tags = page.select('[class~=text]')
    for tag in tags:
        # If the text element of the node matches "Libor *" the node has LIBOR
        # data in USD, which is what we want.  We capture the maturity in the
        # RegEx group.
        match = re.match(r'Libor (.*)', tag.text)
        if match:
            maturity = match.group(1)
            # We need to back up the parent (table row) of the table data and
            # grab the first node with a class of "num" as that will be the
            # latest published LIBOR for that maturity.
            rate = tag.parent.select_one('[class~=num]')
            if rate is not None:
                rates[maturity_mapping[maturity]] = rate.text

    # Now that we have retrieved the data, submit it
    print 'Submitting LIBOR for effective date: {}'.format(date.isoformat())
    for maturity, rate in rates.items():
        print '{0} => {1}'.format(maturity, rate)

    if args.url:
        config.set('DEFAULT', 'url', args.url)

    client = LIBORClient(
        base_url=config.get('DEFAULT', 'url'),
        key_file=config.get('DEFAULT', 'key_file'),
        libor_key_file=args.keyfile)

    client.submit_rates(date, rates)
    if args.wait:
        client.wait_for_commit()


def do_list(args, config):
    if args.url:
        config.set('DEFAULT', 'url', args.url)

    client = LIBORClient(
        base_url=config.get('DEFAULT', 'url'),
        key_file=config.get('DEFAULT', 'key_file'))

    client.fetch_state()
    state = client.get_state()

    if args.date is None:
        print '+----------+---------+--------+--------+--------+--------+'\
            '--------+--------+'
        print '|   Date   |Overnight| 1 Week | 1 Month| 2 Month| 3 Month|'\
            ' 6 Month| 1 Year |'
        print '+----------+---------+--------+--------+--------+--------+'\
            '--------+--------+'
        libor_data = state.get_all_by_object_type('libor')
        for libor in sorted(libor_data, key=lambda x: x['date']):
            rates = libor['rates']
            print '|{0}|{1:> 9.4f}|{2:> 8.4f}|{3:> 8.4f}|{4:> 8.4f}'\
                '|{5:> 8.4f}|{6:> 8.4f}|{7:> 8.4f}|'.format(
                    libor['date'],
                    rates['Overnight'],
                    rates['OneWeek'],
                    rates['OneMonth'],
                    rates['TwoMonth'],
                    rates['ThreeMonth'],
                    rates['SixMonth'],
                    rates['OneYear'])
        print '+----------+---------+--------+--------+--------+--------+'\
            '--------+--------+'
    else:
        date_string = args.date.isoformat()
        try:
            libor = state.lookup('libor:date', date_string)
            rates = libor['rates']

            print '|---------------------+'
            print '|LIBOR for {} |'.format(libor['date'])
            print '|------------+--------+'
            print '|Overnight:  |{:> 8.4f}|'.format(rates['Overnight'])
            print '|------------+--------+'
            print '|1 Week:     |{:> 8.4f}|'.format(rates['OneWeek'])
            print '|------------+--------+'
            print '|1 Month:    |{:> 8.4f}|'.format(rates['OneMonth'])
            print '|------------+--------+'
            print '|2 Month:    |{:> 8.4f}|'.format(rates['TwoMonth'])
            print '|------------+--------+'
            print '|3 Month:    |{:> 8.4f}|'.format(rates['ThreeMonth'])
            print '|------------+--------+'
            print '|6 Month:    |{:> 8.4f}|'.format(rates['SixMonth'])
            print '|------------+--------+'
            print '|1 Year:     |{:> 8.4f}|'.format(rates['OneYear'])
            print '|------------+--------+'
        except KeyError:
            print 'No rate data for {}'.format(date_string)


def load_config():
    home = os.path.expanduser("~")
    real_user = getpass.getuser()

    config_file = os.path.join(home, ".sawtooth", "libor.cfg")
    key_dir = os.path.join(home, ".sawtooth", "keys")

    config = ConfigParser.SafeConfigParser()
    config.set('DEFAULT', 'url', 'http://localhost:8800')
    config.set('DEFAULT', 'key_dir', key_dir)
    config.set('DEFAULT', 'key_file', '%(key_dir)s/%(username)s.wif')
    config.set('DEFAULT', 'username', real_user)

    # If we already have a config file, then read it.  Otherwise,
    # we are going to write a default one.
    if os.path.exists(config_file):
        config.read(config_file)
    else:
        if not os.path.exists(os.path.dirname(config_file)):
            os.makedirs(os.path.dirname(config_file))

        with open("{}.new".format(config_file), "w") as fd:
            config.write(fd)
        os.rename("{}.new".format(config_file), config_file)

    # If the key file does not already exist, then we are going
    # to generate one
    wif_filename = config.get('DEFAULT', 'key_file')
    if wif_filename.endswith(".wif"):
        addr_filename = wif_filename[0:-len(".wif")] + ".addr"
    else:
        addr_filename = wif_filename + ".addr"

    if not os.path.exists(wif_filename):
        try:
            if not os.path.exists(os.path.dirname(wif_filename)):
                os.makedirs(os.path.dirname(wif_filename))

            private_key = pybitcointools.random_key()
            encoded_key = pybitcointools.encode_privkey(private_key, 'wif')
            addr = pybitcointools.privtoaddr(private_key)

            with open(wif_filename, "w") as wif_fd:
                wif_fd.write(encoded_key)
                wif_fd.write("\n")

            with open(addr_filename, "w") as addr_fd:
                addr_fd.write(addr)
                addr_fd.write("\n")
        except IOError as ioe:
            raise LIBORClientException("IOError: {}".format(str(ioe)))

    return config


def main(prog_name=os.path.basename(sys.argv[0]), args=sys.argv[1:]):
    parser = create_parser(prog_name)
    args = parser.parse_args(args)

    if args.verbose is None:
        verbose_level = 0
    else:
        verbose_level = args.verbose

    setup_loggers(verbose_level=verbose_level)

    config = load_config()

    commands = {
        'submit': do_submit,
        'list': do_list
    }
    commands[args.command](args, config)


def main_wrapper():
    # pylint: disable=bare-except
    try:
        main()
    except LIBORClientException as e:
        print >>sys.stderr, "Error: {}".format(e)
        sys.exit(1)
    except KeyboardInterrupt:
        pass
    except SystemExit as e:
        raise e
    except:
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
