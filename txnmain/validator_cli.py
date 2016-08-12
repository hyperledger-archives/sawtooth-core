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
import json
import yaml
import logging.config
import os
import sys
import traceback
import warnings

from sawtooth.config import ArgparseOptionsConfig
from sawtooth.config import ConfigFileNotFound
from sawtooth.config import InvalidSubstitutionKey
from txnserver import log_setup
from txnserver.config import get_validator_configuration

logger = logging.getLogger(__name__)

CurrencyHost = os.environ.get("HOSTNAME", "localhost")


def local_main(config, windows_service=False, daemonized=False):
    """
    Implement the actual application logic for starting the
    txnvalidator
    """

    # If this process has been daemonized, then we want to make
    # sure to print out an information message as quickly as possible
    # to the logger for debugging purposes.
    if daemonized:
        logger.info('validator has been daemonized')

    # These imports are delayed because of poor interactions between
    # epoll and fork.  Unfortunately, these import statements set up
    # epoll and we need that to happen after the forking done with
    # Daemonize().  This is a side-effect of importing twisted.
    from twisted.internet import reactor
    from txnserver import lottery_validator
    from txnserver import quorum_validator
    from txnserver import web_api
    from gossip.gossip_core import GossipException

    logger.warn('validator pid is %s', os.getpid())

    ledgertype = config.get('LedgerType', 'lottery')

    validator = None

    try:
        if ledgertype == 'lottery':
            validator = lottery_validator.LotteryValidator(
                config,
                windows_service=windows_service)
        elif ledgertype == 'quorum':
            validator = quorum_validator.QuorumValidator(
                config,
                windows_service=windows_service)
        else:
            warnings.warn('Unknown ledger type %s' % ledgertype)
            sys.exit(1)
    except GossipException as e:
        print >> sys.stderr, str(e)
        sys.exit(1)

    web_api.initialize_web_server(config, validator)

    # go through the list of transaction families that should be initialized in
    # this validator. the endpoint registry is always included
    for txnfamily in config.get('TransactionFamilies'):
        logger.info("adding transaction family: %s", txnfamily)
        try:
            validator.add_transaction_family(
                importlib.import_module(txnfamily))
        except ImportError:
            warnings.warn("transaction family not found: {}".format(txnfamily))
            sys.exit(1)

    try:
        validator.pre_start()

        reactor.run()
    except KeyboardInterrupt:
        pass
    except SystemExit as e:
        raise e
    except:
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


def parse_command_line(args):
    parser = argparse.ArgumentParser()

    parser.add_argument('--config',
                        help='Comma-separated list of config files to '
                             'load. Alternatively, multiple --config '
                             'options can be specified.',
                        action='append')
    parser.add_argument('--keyfile', help='Name of the key file')
    parser.add_argument('--conf-dir', help='Name of the config directory')
    parser.add_argument('--data-dir', help='Name of the data directory')
    parser.add_argument('--daemon',
                        help='Daemonize this process',
                        action='store_true')
    parser.add_argument(
        '--delay-start',
        help='Delay full startup sequence until /command/start',
        action='store_true', default=False)
    parser.add_argument('--log-config', help='The python logging config file')
    parser.add_argument('--peers',
                        help='Comma-separated list of peers to connect to. '
                             'Alternatively, multiple --peers options can '
                             'be specified.',
                        action='append')
    parser.add_argument('--genesis',
                        help='Start the ledger with the genesis block',
                        action='store_true')
    parser.add_argument(
        '--url',
        help='Comma-separated list of URLs from which to retrieve peer '
             'list or **none** for no url. Alternatively, multiple --url '
             'options can be specified.',
        action='append')
    parser.add_argument('--node', help='Short form name of the node')
    parser.add_argument('--restore',
                        help='Restore previous block chain',
                        action='store_true')
    parser.add_argument('--type', help='Type of ledger to create')
    parser.add_argument('-v', '--verbose',
                        action='count',
                        default=0,
                        help='increase output sent to stderr')
    parser.add_argument('--run-dir', help='Name of the run directory')
    parser.add_argument('--pidfile', help='Name of the PID file')
    parser.add_argument('--listen',
                        help='An IP/port/protocol combination the validator '
                             'will listen on.  Multiple --listen options can '
                             'be specified.',
                        action='append')

    result = parser.parse_args(args)

    # Set the default value of config because argparse 'default' in
    # combination with action='append' does the wrong thing.
    if result.config is None:
        result.config = ['txnvalidator.js']

    # Convert any comma-delimited argument strings to list elements
    for arglist in [result.config, result.peers, result.url]:
        if arglist is not None:
            for arg in arglist:
                if ',' in arg:
                    loc = arglist.index(arg)
                    arglist.pop(loc)
                    for element in reversed(arg.split(',')):
                        arglist.insert(loc, element)

    # if the boolean arguments have not been set to true, remove
    # them to prevent the False value from overriding during aggregation

    remove_false_key(result, "genesis")
    remove_false_key(result, "restore")
    remove_false_key(result, "daemon")

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
            ('data_dir', 'DataDirectory'),
            ('delay_start', 'DelayStart'),
            ('run_dir', 'RunDirectory'),
            ('type', 'LedgerType'),
            ('log_config', 'LogConfigFile'),
            ('keyfile', 'KeyFile'),
            ('node', 'NodeName'),
            ('restore', 'Restore'),
            ('peers', 'Peers'),
            ('genesis', 'GenesisLedger'),
            ('url', 'LedgerURL'),
            ('verbose', 'Verbose'),
            ('pidfile', 'PidFile'),
            ('daemon', 'Daemonize'),
            ('listen', 'Listen')
        ], options)

    return get_validator_configuration(options.config, options_config, os_name,
                                       config_files_required)


def log_configuration(cfg):
    if 'LogConfigFile' in cfg and \
            isinstance(cfg['LogConfigFile'], basestring) and \
            len(cfg['LogConfigFile']) > 0:
        log_config_file = cfg['LogConfigFile']
        if log_config_file.split(".")[-1] == "js":
            try:
                with open(log_config_file) as log_config_fd:
                    log_dic = json.load(log_config_fd)
                    logging.config.dictConfig(log_dic)
            except IOError, ex:
                print >>sys.stderr, "Could not read log config: {}" \
                    .format(str(ex))
                sys.exit(1)
        elif log_config_file.split(".")[-1] == "yaml":
            try:
                with open(log_config_file) as log_config_fd:
                    log_dic = yaml.load(log_config_fd)
                    logging.config.dictConfig(log_dic)
            except IOError, ex:
                print >>sys.stderr, "Could not read log config: {}"\
                    .format(str(ex))
                sys.exit(1)
        else:
            print >>sys.stderr, "LogConfigFile type not supported: {}"\
                .format(cfg['LogConfigFile'])
            sys.exit(1)

    else:
        log_filename = os.path.join(cfg["LogDirectory"], cfg["NodeName"])
        flogD = logging.FileHandler(log_filename + "-debug.log")
        flogD.setFormatter(logging.Formatter(
            '[%(asctime)s %(name)s %(levelname)s] %(message)s', "%H:%M:%S"))
        flogD.setLevel(logging.DEBUG)

        flogE = logging.FileHandler(log_filename + "-error.log")
        flogE.setFormatter(logging.Formatter(
            '[%(asctime)s %(name)s %(levelname)s] %(message)s', "%H:%M:%S"))
        flogE.setLevel(logging.ERROR)

        logging.getLogger().addHandler(flogE)
        logging.getLogger().addHandler(flogD)


def read_key_file(keyfile):
    with open(keyfile, "r") as fd:
        key = fd.read().strip()
    return key


if os.name == "nt":
    import win32service
    import win32serviceutil
    import win32event
    import servicemanager
    from twisted.internet import reactor

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

    if 'LogLevel' in cfg:
        print >>sys.stderr, "LogLevel is no longer supported, use " \
            "LogConfigFile instead"
        sys.exit(1)

    if 'LogFile' in cfg:
        print >>sys.stderr, "LogFile is no longer supported, use " \
            "LogConfigFile instead"
        sys.exit(1)

    daemonize = cfg.get('Daemonize', False)
    if daemonize:
        verbose_level = 0
    else:
        verbose_level = cfg['Verbose']

    log_configuration(cfg)
    log_setup.setup_loggers(
        verbose_level=verbose_level,
        capture_std_output=daemonize)

    for key, value in cfg.iteritems():
        logger.debug("CONFIG: %s = %s", key, value)

    logger.info('validator started with arguments: %s', sys.argv)

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

    if daemonize:
        if os.name != 'posix':
            warnings.warn("Running as a daemon is not supported on "
                          "non-posix platforms")
            sys.exit(1)

        try:
            from daemonize import Daemonize
        except ImportError, e:
            warnings.warn("Configured to run as a daemon, but import from "
                          "'daemonize' failed: {}".format(str(e)))
            sys.exit(1)

        pid_dir = os.path.dirname(cfg["PidFile"])
        if not os.path.exists(pid_dir):
            warnings.warn("can not create PID file, no such directory: "
                          "{}".format(pid_dir))

    keep_fds = []
    for handler in logging.getLogger().handlers:
        keep_fds.append(handler.stream.fileno())

    if cfg.get("Daemonize", False):
        daemon = Daemonize(
            app="txnvalidator",
            pid=os.path.join(cfg["PidFile"]),
            action=lambda: local_main(cfg, windows_service, daemonized=True),
            keep_fds=keep_fds)
        daemon.start()
    else:
        local_main(cfg, windows_service)


def main_wrapper():
    if (os.name == "nt" and len(sys.argv) > 1
            and sys.argv[1] in ['start', 'stop', 'install', 'remove',
                                '--startup=auto']):
        win32serviceutil.HandleCommandLine(SawtoothValidatorService)
    else:
        main(sys.argv[1:])
