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
import importlib
import logging
import os
import sys
import warnings

from twisted.internet import reactor

from gossip.config import ArgparseOptionsConfig
from gossip.config import ConfigFileNotFound
from gossip.config import InvalidSubstitutionKey
from txnserver import log_setup, lottery_validator, voting_validator, web_api
from txnserver.config import get_validator_configuration

logger = logging.getLogger(__name__)

CurrencyHost = os.environ.get("HOSTNAME", "localhost")


def local_main(config, windows_service=False):
    """
    Implement the actual application logic for starting the
    txnvalidator
    """
    ledgertype = config.get('LedgerType', 'lottery')
    if ledgertype == 'lottery':
        validator = lottery_validator.LotteryValidator(
            config,
            windows_service=windows_service)
    elif ledgertype == 'voting':
        validator = voting_validator.VotingValidator(
            config,
            windows_service=windows_service)
    else:
        warnings.warn('Unknown ledger type %s' % ledgertype)
        sys.exit(1)

    web_api.initialize_web_server(config, validator.Ledger)

    # go through the list of transaction families that should be initialized in
    # this validator. the endpoint registry is always included
    for txnfamily in config.get('TransactionFamilies'):
        try:
            validator.add_transaction_family(
                importlib.import_module(txnfamily))
        except ImportError:
            warnings.warn("transaction family not found: {}".format(txnfamily))
            sys.exit(1)

    validator.start()

    reactor.run()


def parse_command_line(args):
    parser = argparse.ArgumentParser()

    parser.add_argument('--config',
                        help='configuration file',
                        default=['txnvalidator.js'],
                        nargs='+')
    parser.add_argument('--loglevel', help='Logging level')
    parser.add_argument('--keyfile', help='Name of the key file')
    parser.add_argument('--conf-dir', help='Name of the config directory')
    parser.add_argument('--data-dir', help='Name of the data directory')
    parser.add_argument('--log-dir', help='Name of the log directory')
    parser.add_argument(
        '--logfile',
        help='Name of the log file, __screen__ for standard output')
    parser.add_argument('--peers',
                        help='Specific list of peers to connect',
                        nargs='+')
    parser.add_argument('--genesis',
                        help='Start the ledger with the genesis block',
                        action='store_true')
    parser.add_argument(
        '--url',
        help='URL from which to retrieve peer list or **none** for no url')
    parser.add_argument('--node', help='Short form name of the node')
    parser.add_argument('--host',
                        help='Host name to use to access specific interface')
    parser.add_argument('--port', help='UDP port to use', type=int)
    parser.add_argument('--http',
                        help='Port on which to run the http server',
                        type=int)
    parser.add_argument('--restore',
                        help='Restore previous block chain',
                        action='store_true')
    parser.add_argument('--set',
                        help='Specify arbitrary configuration options',
                        nargs=2,
                        action='append')
    parser.add_argument('--type', help='Type of ledger to create')

    result = parser.parse_args(args)

    # if the boolean arguments have not been set to true, remove
    # them to prevent the False value from overriding during aggregation

    remove_false_key(result, "genesis")
    remove_false_key(result, "restore")

    return result


def remove_false_key(namespace, key):
    """
    If key is in the namespace and has a value of False, remove it.
    :param namespace: The namespace
    :param key: The key
    :return: None. The namespace passed in the argument is
    modified in place.
    """
    if key in namespace.__dict__ and not namespace.__dict__[key]:
        del namespace.__dict__[key]

    return None


def get_configuration(args, os_name=os.name, config_files_required=True):
    options = parse_command_line(args)

    options_config = ArgparseOptionsConfig(
        [
            ('conf_dir', 'ConfigDirectory'),
            ('log_dir', 'LogDirectory'),
            ('data_dir', 'DataDirectory'),
            ('type', 'LedgerType'),
            ('logfile', 'LogFile'),
            ('loglevel', 'LogLevel'),
            ('keyfile', 'KeyFile'),
            ('node', 'NodeName'),
            ('host', 'Host'),
            ('port', 'Port'),
            ('http', 'HttpPort'),
            ('restore', 'Restore'),
            ('peers', 'Peers'),
            ('genesis', 'GenesisLedger'),
            ('url', 'LedgerURL'),
        ], options)

    if "LogLevel" in options_config:
        options_config["LogLevel"] = options_config["LogLevel"].upper()

    return get_validator_configuration(options.config, options_config, os_name,
                                       config_files_required)


def read_key_file(keyfile):
    with open(keyfile, "r") as fd:
        key = fd.read().strip()
    return key


if os.name == "nt":
    import win32service
    import win32serviceutil
    import win32event
    import servicemanager

    class SawtoothValidatorService(win32serviceutil.ServiceFramework):
        _svc_name_ = "SawtoothValidator-Service"
        _svc_display_name_ = "SawtoothLake Validator"
        _svc_description_ = "Sawtooth Lake Transaction Validator"

        def __init__(self, args):
            win32serviceutil.ServiceFramework.__init__(self, args)
            self.stop_event = win32event.CreateEvent(None, 0, 0, None)
            self.stop_requested = False

        def SvcStop(self):
            # pylint: disable=invalid-name

            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            logger.warn('received shutdown signal')
            reactor.stop()
            self.ReportServiceStatus(win32service.SERVICE_STOPPED)
            self.stop_requested = True

        def SvcDoRun(self):
            # pylint: disable=invalid-name

            servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                                  servicemanager.PYS_SERVICE_STARTED,
                                  (self._svc_name_, ''))
            main([], windows_service=True)


def main(args, windows_service=False):
    try:
        cfg = get_configuration(args)
    except ConfigFileNotFound, e:
        print >> sys.stderr, str(e)
        sys.exit(1)
    except InvalidSubstitutionKey, e:
        print >> sys.stderr, str(e)
        sys.exit(1)

    log_setup.setup_loggers(cfg)

    for key, value in cfg.iteritems():
        logger.debug("CONFIG: {} = {}".format(key, value))

    logger.info('validator started with arguments: %s', sys.argv)
    logger.warn('validator pid is %s', os.getpid())

    if not os.path.exists(cfg["DataDirectory"]):
        warnings.warn("Data directory does not exist: {}".format(
            cfg["DataDirectory"]))
        sys.exit(1)

    if "KeyFile" in cfg:
        keyfile = cfg["KeyFile"]
        if os.path.isfile(keyfile):
            logger.info('read signing key from %s', keyfile)
            key = read_key_file(keyfile)
            cfg['SigningKey'] = key
        else:
            logger.warn('unable to find locate key file %s', keyfile)
    else:
        logger.warn('no key file specified')

    local_main(cfg, windows_service)


def main_wrapper():
    if (os.name == "nt" and len(sys.argv) > 1
            and sys.argv[1] in ['start', 'stop', 'install', 'remove']):
        win32serviceutil.HandleCommandLine(SawtoothValidatorService)
    else:
        main(sys.argv[1:])
