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

import subprocess
import signal
import urllib2
import os
import sys
import re
import json

from txnintegration.exceptions import ValidatorManagerException
from txnintegration.utils import generate_private_key
from txnintegration.utils import get_address_from_private_key_wif
from txnintegration.utils import human_size
from txnintegration.utils import read_key_file
from gossip.messages import shutdown_message
from sawtooth.client import LedgerWebClient
from sawtooth.exceptions import MessageException


class ValidatorManager(object):
    """
    Manages a txnvalidator process
    contains logic to:
     - launch
     - shutdown
     - check status
     - detect errors
     - report log, stderr, and strout
    """

    def __init__(self,
                 txn_validator,
                 config,
                 data_dir,
                 admin_node,
                 log_config):
        self._txn_validator = txn_validator
        self.id = config['id']
        self.name = config['NodeName']
        self.config = config
        self.log_config = log_config
        self._admin_node = admin_node

        self._data_dir = data_dir

        # Generate key for validator
        self._key = generate_private_key()
        self._address = get_address_from_private_key_wif(self._key)

        self.url = None
        self._command = None
        self._stdout_file = None
        self._output = None
        self._stderr_file = None
        self._outerr = None
        self._config_file = None
        self._log_file = None
        self._handle = None

    def launch(self, launch=True, genesis=False, daemon=False, delay=False):
        self.url = "http://{}:{}".format(self.config['Host'],
                                         self.config['HttpPort'])

        self.config['LogDirectory'] = self._data_dir
        self._log_file = os.path.join(self._data_dir,
                                      "{}.log".format(self.name))

        if os.path.exists(self._log_file):  # delete existing log file
            os.remove(self._log_file)

        self.config['KeyFile'] = os.path.join(self._data_dir,
                                              "{}.wif".format(self.name))
        if not os.path.isfile(self.config['KeyFile']):
            with open(self.config['KeyFile'], 'w') as fp:
                fp.write(self._key)
                fp.write("\n")
        else:
            self._key = read_key_file(self.config['KeyFile'])
            self._address = get_address_from_private_key_wif(self._key)

        if self.log_config:
            for v in self.log_config["handlers"].itervalues():
                if 'filename' in v:
                    filename = os.path.join(
                        self._data_dir,
                        "{}-{}".format(self.name,
                                       os.path.basename(v['filename'])))
                    v['filename'] = filename

            log_config_file = os.path.join(self._data_dir,
                                           "{}-log-config.js"
                                           .format(self.name))
            with open(log_config_file, 'w') as fp:
                json.dump(self.log_config, fp)
            self.config['LogConfigFile'] = log_config_file

        config_file_name = "{}.json".format(self.name)
        self._config_file = os.path.join(self._data_dir, config_file_name)
        with open(self._config_file, 'w') as fp:
            json.dump(self.config, fp)

        args = [
            sys.executable,  # Fix for windows, where script are not executable
            self._txn_validator,
            "--conf-dir",
            self._data_dir,
            "--config",
            config_file_name
        ]

        if genesis:
            args.append("--genesis")

        if daemon:
            args.append("--daemon")

        if delay:
            args.append("--delay-start")

        # redirect stdout and stderror
        self._stdout_file = os.path.join(self._data_dir,
                                         "{}.out".format(self.name))
        self._stderr_file = os.path.join(self._data_dir,
                                         "{}.err".format(self.name))

        self._command = " ".join(args)
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(sys.path)
        if launch:
            self._output = open(self._stdout_file, 'w')
            self._outerr = open(self._stderr_file, 'w')
            self._handle = subprocess.Popen(args,
                                            stdout=self._output,
                                            stderr=self._outerr,
                                            env=env)
        else:
            self._handle = None

    def is_registered(self, url=None):
        if not url:
            url = self.url
        url = "{}/store/EndpointRegistryTransaction".format(url)

        try:
            response = urllib2.urlopen(url)
        except:
            return False

        content = response.read()
        headers = response.info()
        response.close()
        if ('Content-Type' not in headers
                or headers['Content-Type'] != 'application/json'):
            return False

        id_list = json.loads(content)
        if id_list is not None:
            return self._address in id_list

        return False

    def shutdown(self, force=False):
        if self._handle:
            self._handle.poll()
            if not self._handle.returncode:
                if force:
                    try:
                        if os.name == "nt":
                            self._handle.kill()
                        else:
                            self._handle.send_signal(signal.SIGKILL)
                    except OSError:
                        pass  # ignore invalid process and other os type errors
                else:
                    try:
                        if os.name == "nt":
                            self._handle.terminate()
                        else:
                            self._handle.send_signal(signal.SIGINT)
                    except OSError:
                        pass
        if self._output and not self._output.closed:
            self._output.close()
        if self._outerr and not self._outerr.closed:
            self._outerr.close()

    def post_shutdown(self):
        lwc = LedgerWebClient(self.Url)

        msg = shutdown_message.ShutdownMessage({})
        msg.SenderID = self._admin_node.Address
        msg.sign_from_node(self._admin_node)

        try:
            lwc.post_message(msg)
        except MessageException as me:
            print me

    def is_running(self):
        if self._handle:
            return self._handle.returncode is None
        return False

    def check_error(self):
        if self._handle:
            if self._handle.returncode:
                raise ValidatorManagerException("validator has exited")
            else:
                if "PYCHARM_HOSTED" not in os.environ:
                    err = os.stat(self._stderr_file)
                    if err.st_size > 0:
                        with open(self._stderr_file, 'r') as fd:
                            lines = fd.readlines()
                            raise ValidatorManagerException(
                                "stderr has output: line 1 of {}: {}".format(
                                    len(lines), lines[0]))
                    self._check_log_error()
        else:
            raise ValidatorManagerException("validator not running")

    def _check_log_error(self):
        if os.path.exists(self._log_file):
            reg = re.compile(r"^\[[\d:]*, ([\d]*), .*\]")
            with open(self._log_file, 'r') as fin:
                for line in fin:
                    match = reg.search(line)
                    if match and int(match.group(1)) >= 50:
                        raise ValidatorManagerException(
                            "error in log: {}".format(line))
                    elif 'error' in line:
                        raise ValidatorManagerException(
                            "error in log: {}".format(line))
                    elif 'Traceback' in line:  # exception dump
                        raise ValidatorManagerException(
                            "error in log: {}".format(line))
                    elif 'exception' in line and \
                            'http request' not in line:
                        #  errors in http requests are routinely generated
                        # when checking transactions status.
                        raise ValidatorManagerException(
                            "error in log: {}".format(line))

    def status(self):
        st = "unk  "
        if self._handle:
            rc = self._handle.returncode
            if rc:
                st = " rc:{}".format(rc)
            else:
                st = " pid:{}".format(self._handle.pid)

        log = ""
        if os.path.exists(self._log_file):
            s = os.stat(self._log_file)
            if s.st_size > 0:
                log = "log: {}".format(human_size(s.st_size))
        out = ""
        if os.path.exists(self._stdout_file):
            s = os.stat(self._stdout_file)
            if s.st_size > 0:
                out = "out: {}".format(human_size(s.st_size))
        err = ""
        if os.path.exists(self._stderr_file):
            s = os.stat(self._stderr_file)
            if s.st_size > 0:
                err = "err: {}".format(human_size(s.st_size))
        errors = ""
        try:
            self.check_error()
        except ValidatorManagerException:
            errors = "errs!"

        return "{}: {} {} {} {} {}".format(self.id, st, out, err, log, errors)

    def dump_config(self):
        with open(self._config_file, 'r') as fin:
            print fin.read()

    def dump_log(self):
        if os.path.exists(self._log_file):
            with open(self._log_file, 'r') as fin:
                print fin.read()

    def dump_stdout(self):
        if os.path.exists(self._stdout_file):
            with open(self._stdout_file, 'r') as fin:
                print fin.read()

    def dump_stderr(self):
        if os.path.exists(self._stderr_file):
            with open(self._stderr_file, 'r') as fin:
                print fin.read()
