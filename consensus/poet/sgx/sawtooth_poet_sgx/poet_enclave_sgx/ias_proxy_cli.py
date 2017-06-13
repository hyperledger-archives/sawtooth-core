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

import argparse
import logging
import pprint
import sys

import os
from colorlog import ColoredFormatter
from util.utils import parse_configuration_file
import ias_proxy

logger = logging.getLogger(__name__)
pp = pprint.PrettyPrinter(indent=4)


def parse_args(args):
    parser = argparse.ArgumentParser()

    # use system or dev paths...
    parser.add_argument(
        '-c',
        '--config',
        help='config file',
        default=None)
    parser.add_argument('--log-level', help='Logging level', default='DEBUG')
    parser.add_argument('--log-file', help='Logging file', default=None,
                        type=str)
    parser.add_argument(
        '-v',
        '--verbose',
        dest="Verbose",
        help='config file',
        action='store_true',
        default=False)
    return vars(parser.parse_args(args))


def configure(args):
    opts = parse_args(args)

    if opts["config"] is None:
        script_dir = os.path.dirname(os.path.realpath(__file__))
        search_files = []
        if os.name == "nt":
            search_files.append("c:\\program files\\sawtooth\\etc\\"
                                "ias_proxy.js")
            search_files.append("c:\\sawtooth\\etc\\ias_proxy.js")
        else:
            search_files.append("/etc/sawtooth/ias_proxy.js")

        search_files.append(os.path.realpath(os.path.join(
            script_dir,
            "..",
            "etc",
            "ias_proxy.js")))

        for f in search_files:
            if os.path.exists(f):
                opts["config"] = f
                break

    if not os.path.exists(opts["config"]):
        raise IOError("Config file does not exist: {}".format(
            opts["config"]))

    config = parse_configuration_file(opts["config"])
    opts = {key: value for key, value in opts.items()
            if value is not None}
    config.update(opts)

    if config["Verbose"]:
        print "Configuration:"
        pp.pprint(config)

    return config


def setup_loggers(config):
    global logger
    if 'log_level' in config:
        log_level = getattr(logging, config["log_level"])
    else:
        log_level = logging.WARN
    logger = logging.getLogger()
    logger.setLevel(log_level)

    clog = logging.StreamHandler()
    formatter = ColoredFormatter(
        '%(log_color)s[%(asctime)s %(module)s]%(reset)s '
        '%(white)s%(message)s',
        datefmt="%H:%M:%S",
        reset=True,
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red',
            'SECRET': 'black'
        })

    clog.setFormatter(formatter)
    clog.setLevel(log_level)
    logger.addHandler(clog)

    if 'log_file' in config:
        flog = logging.FileHandler(config['log_file'])
        logger.addHandler(flog)
    else:
        flog = logging.FileHandler('ias_proxy.log')
        logger.addHandler(flog)
        logger.warn('Log file not specified. Guess you found it though.')

    logger.info("Logger Initialized!")
    logger.info("Config: %s" % config)

# Global server instance
server = None


def server_main(args=[]):
    global server
    config = configure(args)
    setup_loggers(config)
    server = ias_proxy.get_server(config)
    server.run()

if os.name == "nt":
    # pylint: disable=wrong-import-order,wrong-import-position
    import servicemanager
    import win32serviceutil

    class SawtoothIasProxyService(win32serviceutil.ServiceFramework):
        _svc_name_ = "Sawtooth Lake IAS Proxy"
        _svc_display_name_ = "Sawtooth Lake IAS Proxy"
        _svc_description_ = "Relays calls to Intel Attestation Service"

        def __init__(self, args):
            win32serviceutil.ServiceFramework.__init__(self, args)
            servicemanager.LogInfoMsg("Starting IAS Proxy Server {}"
                                      .format(args))

        def SvcStop(self):
            # pylint: disable=invalid-name
            global server
            logger.warn('received shutdown signal')
            server.stop()

        def SvcDoRun(self):
            # pylint: disable=invalid-name
            global server
            server_main([])


def main(args=sys.argv[1:]):
    service_args = ['start', 'stop', 'install', 'remove']
    service_mode = False
    if (os.name == "nt" and len(sys.argv)) > 1:
        for arg in sys.argv[1:]:
            if arg in service_args:
                service_mode = True
    if service_mode:
        win32serviceutil.HandleCommandLine(SawtoothIasProxyService)
    else:
        server_main(args)

if __name__ == '__main__':
    main(args=sys.argv[1:])
