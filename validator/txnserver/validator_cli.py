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
import importlib
import json
import yaml
import logging.config
import os
import sys
import traceback
import warnings
import ctypes

from sawtooth.config import ArgparseOptionsConfig
from sawtooth.config import ConfigFileNotFound
from sawtooth.config import InvalidSubstitutionKey
from sawtooth.validator_config import get_validator_configuration
from txnserver import log_setup

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
    from txnserver.validator import parse_networking_info
    from txnserver.validator import Validator
    from txnserver import web_api
    from gossip.gossip_core import GossipException
    from gossip.gossip_core import Gossip
    from journal.journal_core import Journal

    logger.warn('validator pid is %s', os.getpid())

    consensus_type = config.get('LedgerType', 'poet0')
    stat_domains = {}

    try:
        (node, http_port) = parse_networking_info(config)
        # to construct a validator, we pass it a consensus specific journal
        validator = None
        journal = None
        # Gossip parameters
        minimum_retries = config.get("MinimumRetries")
        retry_interval = config.get("RetryInterval")
        gossip = Gossip(node, minimum_retries, retry_interval, stat_domains)
        # WaitTimer globals
        target_wait_time = config.get("TargetWaitTime")
        initial_wait_time = config.get("InitialWaitTime")
        certificate_sample_length = config.get('CertificateSampleLength')
        fixed_duration_blocks = config.get("FixedDurationBlocks")
        minimum_wait_time = config.get("MinimumWaitTime")
        # Journal parameters
        min_txn_per_block = config.get("MinimumTransactionsPerBlock")
        max_txn_per_block = config.get("MaxTransactionsPerBlock")
        max_txn_age = config.get("MaxTxnAge")
        data_directory = config.get("DataDirectory")
        store_type = config.get("StoreType")

        if consensus_type == 'poet0':
            from sawtooth_validator.consensus.poet0 import poet_consensus
            from sawtooth_validator.consensus.poet0.wait_timer \
                import set_wait_timer_globals
            set_wait_timer_globals(target_wait_time,
                                   initial_wait_time,
                                   certificate_sample_length,
                                   fixed_duration_blocks)
            # Continue to pass config to PoetConsensus for possible other
            # enclave implementations - poet_enclave.initialize
            consensus = poet_consensus.PoetConsensus(config)
        elif consensus_type == 'poet1':
            from sawtooth_validator.consensus.poet1 import poet_consensus
            from sawtooth_validator.consensus.poet1.wait_timer \
                import set_wait_timer_globals
            set_wait_timer_globals(target_wait_time,
                                   initial_wait_time,
                                   certificate_sample_length,
                                   fixed_duration_blocks,
                                   minimum_wait_time)
            # Continue to pass config to PoetConsensus for possible other
            # enclave implementations - poet_enclave.initialize
            consensus = poet_consensus.PoetConsensus(config)
        elif consensus_type == 'dev_mode':
            block_publisher = config.get("DevModePublisher", False)
            block_wait_time = config.get("BlockWaitTime")
            from sawtooth_validator.consensus.dev_mode \
                import dev_mode_consensus
            consensus = dev_mode_consensus.DevModeConsensus(
                block_publisher,
                block_wait_time)
        else:
            warnings.warn('Unknown consensus type %s' % consensus_type)
            sys.exit(1)

        permissioned_validators =\
            config.get("WhitelistOfPermissionedValidators")

        journal = Journal(
            gossip.LocalNode,
            gossip,
            gossip.dispatcher,
            consensus,
            permissioned_validators,
            stat_domains,
            min_txn_per_block,
            max_txn_per_block,
            max_txn_age,
            data_directory,
            store_type)

        validator = Validator(
            gossip,
            journal,
            stat_domains,
            config,
            windows_service=windows_service,
            http_port=http_port,
        )
    except GossipException as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    listen_info = config.get("Listen", None)
    web_api.initialize_web_server(listen_info, validator)

    # go through the list of transaction families that should be initialized in
    # this validator. the endpoint registry is always included
    if consensus_type == 'poet1':
        from sawtooth_validator.consensus.poet1 import validator_registry
        validator_registry.register_transaction_types(journal)
    for txnfamily in config.get('TransactionFamilies'):
        logger.info("adding transaction family: %s", txnfamily)
        try:
            validator.add_transaction_family(
                importlib.import_module(txnfamily))
        except ImportError:
            warnings.warn("transaction family not found: {}".format(txnfamily))
            sys.exit(1)

    # attempt to restore journal state from persistence
    try:
        validator.journal.restore()
    except KeyError as e:
        logger.error("Config is not compatible with data files"
                     " found on restore. Keyerror on %s", e)
        sys.exit(1)

    try:
        validator.pre_start()

        reactor.run(installSignalHandlers=False)
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
    parser.add_argument(
        '--url',
        help='Comma-separated list of URLs from which to retrieve peer '
             'list or **none** for no url. Alternatively, multiple --url '
             'options can be specified.',
        action='append')
    parser.add_argument('--node', help='Short form name of the node')
    parser.add_argument('--type', help='Type of ledger to create')
    parser.add_argument('-v', '--verbose',
                        action='count',
                        default=0,
                        help='Increase output sent to stderr')
    parser.add_argument('--run-dir', help='Name of the run directory')
    parser.add_argument('--pidfile', help='Name of the PID file')
    parser.add_argument('--listen',
                        help='An IP/port/protocol combination the validator '
                             'will listen on.  Multiple --listen options can '
                             'be specified.',
                        action='append')
    parser.add_argument('--check-elevated',
                        help='Check for elevated privilege level',
                        default=False)
    parser.add_argument('-F', '--family',
                        help='Specify transaction families to load. Multiple'
                             ' -F options can be specified.',
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

    remove_false_key(result, "daemon")
    remove_false_key(result, "check_elevated")

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


def get_configuration(args, os_name=os.name, config_files_required=None):
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
            ('peers', 'Peers'),
            ('url', 'LedgerURL'),
            ('verbose', 'Verbose'),
            ('pidfile', 'PidFile'),
            ('daemon', 'Daemonize'),
            ('check_elevated', 'CheckElevated'),
            ('listen', 'Listen'),
            ('family', 'TransactionFamilies')
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
                print("Could not read log config: {}"
                      .format(str(ex)), file=sys.stderr)
                sys.exit(1)
        elif log_config_file.split(".")[-1] == "yaml":
            try:
                with open(log_config_file) as log_config_fd:
                    log_dic = yaml.load(log_config_fd)
                    logging.config.dictConfig(log_dic)
            except IOError, ex:
                print("Could not read log config: {}"
                      .format(str(ex)), file=sys.stderr)
                sys.exit(1)
        else:
            print("LogConfigFile type not supported: {}"
                  .format(cfg['LogConfigFile']), file=sys.stderr)
            sys.exit(1)

    else:
        log_filename = os.path.join(cfg["LogDirectory"], cfg["NodeName"])
        flogD = logging.FileHandler(log_filename + "-debug.log")
        flogD.setFormatter(logging.Formatter(
            '[%(asctime)s [%(threadName)s] %(name)s %(levelname)s] '
            '%(message)s', "%H:%M:%S"))
        flogD.setLevel(logging.DEBUG)

        flogE = logging.FileHandler(log_filename + "-error.log")
        flogE.setFormatter(logging.Formatter(
            '[%(asctime)s [%(threadName)s] %(name)s %(levelname)s] '
            '%(message)s', "%H:%M:%S"))
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
        print(str(e), file=sys.stderr)
        sys.exit(1)
    except InvalidSubstitutionKey, e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    if 'LogLevel' in cfg:
        print("LogLevel is no longer supported, use "
              "LogConfigFile instead", file=sys.stderr)
        sys.exit(1)

    if 'LogFile' in cfg:
        print("LogFile is no longer supported, use "
              "LogConfigFile instead", file=sys.stderr)
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

    check_elevated = cfg.get('CheckElevated')
    if check_elevated is False:
        logger.debug("check for elevated (root/admin) privileges "
                     "is disabled")
    else:
        if os.name == "posix":
            is_admin = os.getuid() == 0
        elif os.name == "nt":
            is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
        else:
            warnings.warn("runnning with elevated (root/admin) privileges is "
                          "not permitted; OS version is unrecognized - "
                          "cannot verify privilege level: %s", os.name)
            sys.exit(1)
        logger.debug("running %s with elevated (root/admin) privileges: %s",
                     os.name, is_admin)
        if is_admin is True:
            warnings.warn("running with elevated (root/admin) privileges "
                          "is not permitted - stopping validator")
            sys.exit(1)

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
            logger.warn('unable to locate key file %s', keyfile)
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
        if hasattr(handler, 'stream'):
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
    if (os.name == "nt" and len(sys.argv) > 1 and
            sys.argv[1] in ['start', 'stop', 'install', 'remove',
                            '--startup=auto']):
        win32serviceutil.HandleCommandLine(SawtoothValidatorService)
    else:
        main(sys.argv[1:])
