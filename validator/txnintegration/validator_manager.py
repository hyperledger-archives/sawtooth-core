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

import subprocess
import signal
import urllib2
import os
import sys
import re
import json

from txnintegration.exceptions import ValidatorManagerException
from txnintegration.utils import human_size
from txnintegration.utils import find_or_create_test_key
from gossip.messages import shutdown_message
from sawtooth.client import SawtoothClient
from sawtooth.exceptions import MessageException
from sawtooth.validator_config import parse_listen_directives


class ValidatorManager(object):
    """
    Manages a txnvalidator process
    contains logic to:
     - launch
     - shutdown
     - check status
     - detect errors
    """

    def __init__(self,
                 txn_validator,
                 config,
                 data_dir,
                 admin_node,
                 log_config,
                 static_node=False):
        self._txn_validator = txn_validator
        self.name = config['NodeName']
        self.config = config
        self.log_config = log_config
        self._admin_node = admin_node
        self.static_node = static_node

        self._data_dir = data_dir

        # Handle validator keys
        key_file = config.get("KeyFile", None)
        if key_file is None:
            key_file = os.path.join(self._data_dir, "{}.wif".format(self.name))
            config["KeyFile"] = key_file
        (_, secret, addr) = find_or_create_test_key(key_file, data_dir)
        self._key = secret
        self._address = addr

        self.url = None
        self._command = None
        self._stdout_file = None
        self._output = None
        self._stderr_file = None
        self._outerr = None
        self._config_file = None
        self._log_file = None
        self._handle = None

    def launch(self, launch=True, daemon=False, delay=False, node=None):
        listen_directives = parse_listen_directives(self.config["Listen"])
        http_host = listen_directives['http'].host
        if "Endpoint" in self.config and self.config['Endpoint'] is not None:
            http_host = self.config["Endpoint"]["Host"]

        self.url = "http://{}:{}".format(http_host,
                                         listen_directives['http'].port)

        self.config['LogDirectory'] = self._data_dir
        self._log_file = os.path.join(self._data_dir,
                                      "{}-debug.log".format(self.name))

        if self.log_config:
            for v in self.log_config["handlers"].itervalues():
                if 'filename' in v:
                    filename = os.path.join(
                        self._data_dir,
                        "{}-{}".format(self.name,
                                       os.path.basename(v['filename'])))
                    v['filename'] = filename
                    # pick the last log file... not sure
                    # how we can pick a better one with out completely
                    # parsing the log config or adding our own entry
                    self._log_file = filename

            log_config_file = os.path.join(self._data_dir,
                                           "{}-log-config.js"
                                           .format(self.name))
            with open(log_config_file, 'w') as fp:
                json.dump(self.log_config, fp, sort_keys=True,
                          indent=4, separators=(',', ': '))
            self.config['LogConfigFile'] = log_config_file

        config_file_name = "{}.json".format(self.name)
        self._config_file = os.path.join(self._data_dir, config_file_name)
        with open(self._config_file, 'w') as fp:
            json.dump(self.config, fp, sort_keys=True,
                      indent=4, separators=(',', ': '))

        args = [
            sys.executable,  # Fix for windows, where script are not executable
            self._txn_validator,
            "--conf-dir",
            self._data_dir,
            "--config",
            config_file_name
        ]

        if daemon:
            args.append("--daemon")

        if delay:
            args.append("--delay-start")

        cmd_file = os.path.join(self._data_dir,
                                "{}.sh"
                                .format(self.name))
        with open(cmd_file, 'w') as fp:
            fp.write('#!/usr/bin/env bash\n')
            fp.write(' '.join(args))
            fp.write('\n')
        os.chmod(cmd_file, 0744)

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
        if ('Content-Type' not in headers or
                headers['Content-Type'] != 'application/json'):
            return False

        id_list = json.loads(content)
        if id_list is not None:
            return self._address in id_list

        return False

    def is_started(self, url=None):
        if not url:
            url = self.url
        client = SawtoothClient(url)
        sta = None
        try:
            sta = client.get_status(timeout=2)
        except MessageException as e:
            print(e.message)
            return False
        if sta is not None:
            return sta.get('Status', '') == 'started'
        return False

    def shutdown(self, force=False, term=False):
        if self._handle:
            self._handle.poll()
            if not self._handle.returncode:
                if term:
                    try:
                        if os.name == "nt":
                            self._handle.terminate()
                        else:
                            self._handle.send_signal(signal.SIGTERM)
                    except OSError:
                        pass
                elif force:
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
        client = SawtoothClient(self.url)

        msg = shutdown_message.ShutdownMessage({})
        msg.SenderID = self._admin_node.Address
        msg.sign_from_node(self._admin_node)

        try:
            client.forward_message(msg)
        except MessageException as me:
            print(me)

    def is_running(self):
        if self._handle:
            self._handle.poll()
            return self._handle.returncode is None
        return False

    def check_error(self):
        if self._handle:
            if self._handle.returncode:
                raise ValidatorManagerException("validator has exited")
            else:
                err = os.stat(self._stderr_file)
                if err.st_size > 0:
                    with open(self._stderr_file, 'r') as fd:
                        lines = fd.readlines()
                        for line in lines:
                            if not (line.startswith('pydev') or
                                    line.strip() == ''):
                                raise ValidatorManagerException(
                                    "stderr has {} lines of output:\n {}"
                                    .format(len(lines), '    '.join(lines)))
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

        return "{} {}: {} {} {} {} {}".format(
            self._address, self.name, st, out, err, log, errors)

    def dump_config(self, out=sys.stdout):
        with open(self._config_file, 'r') as fin:
            print(fin.read(), file=out)

    def dump_log(self, out=sys.stdout):
        if os.path.exists(self._log_file):
            with open(self._log_file, 'r') as fin:
                print(fin.read(), file=out)
                if fin.tell() == 0:
                    print('<empty>', file=out)

    def dump_stdout(self, out=sys.stdout):
        if os.path.exists(self._stdout_file):
            with open(self._stdout_file, 'r') as fin:
                print(fin.read(), file=out)
                if fin.tell() == 0:
                    print('<empty>', file=out)

    def dump_stderr(self, out=sys.stdout):
        if os.path.exists(self._stderr_file):
            with open(self._stderr_file, 'r') as fin:
                print(fin.read(), file=out)
                if fin.tell() == 0:
                    print('<empty>', file=out)
