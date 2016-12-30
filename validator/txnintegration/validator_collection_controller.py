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

import tarfile
import time
import os
from os import walk

from sawtooth_signing import pbct_nativerecover as signing
from txnintegration.exceptions import ExitError
from txnintegration.exceptions import ValidatorManagerException
from txnintegration.matrices import NodeController
from txnintegration.utils import find_executable
from txnintegration.utils import Progress
from txnintegration.utils import TimeOut
from txnintegration.validator_manager import ValidatorManager


class ValidatorCollectionController(NodeController):
    class AdminNode(object):
        """
            This is a stand-in for a node when signing admin messages.
            Hence the non pep8 names.
        """
        def __init__(self):
            self.SigningKey = signing.generate_privkey()
            self.Address = signing.generate_identifier(
                signing.generate_pubkey(self.SigningKey))

    def __init__(self, net_config, txnvalidator=None, log_config=None):
        super(ValidatorCollectionController, self).__init__(net_config.n_mag)
        self.net_config = net_config
        self.hdls = [None for _ in range(net_config.n_mag)]
        self.data_dir = None
        if self.net_config.provider is not None:
            self.data_dir = self.net_config.provider.currency_home
        if txnvalidator is None:
            txnvalidator = find_executable('txnvalidator')
        self.txnvalidator = txnvalidator
        self.validator_log_config = log_config
        self.admin_node = ValidatorCollectionController.AdminNode()

    def active_validators(self):
        return [v for v in self.hdls if v is not None]

    def status(self):
        return [v.status() for v in self.active_validators()]

    def urls(self):
        return [v.url for v in self.active_validators()]

    def activate(self, idx,
                 probe_seconds=0,
                 launch=True,
                 daemon=False,
                 delay=False,
                 **kwargs
                 ):
        sta = self.hdls[idx]
        assert sta is None
        cfg = self.net_config.get_node_cfg(idx)
        cfg["AdministrationNode"] = self.admin_node.Address
        log_config = self.validator_log_config
        if log_config is not None:
            log_config = self.validator_log_config.copy()
        v = ValidatorManager(self.txnvalidator,
                             cfg,
                             self.data_dir,
                             self.admin_node,
                             log_config,
                             static_node=True,
                             )
        print('launching %s...' % (v.name), end=' ')
        v.launch(launch, daemon=daemon, delay=delay)
        if probe_seconds > 0:
            self.probe_validator(v, max_time=probe_seconds)
        else:
            print()
        self.hdls[idx] = v
        return v

    def deactivate(self, idx, sig='SIGINT', timeout=4, force=True, **kwargs):
        if not isinstance(self.hdls[idx], ValidatorManager):
            raise Exception("node %s does not appear to be runnning" % (idx))
        self.validator_shutdown(idx, sig, timeout, force)
        assert self.hdls[idx] is None

    def commit(self, reg_seconds=240, **kwargs):
        if reg_seconds > 0:
            active = self.active_validators()
            for v in active:
                self.wait_for_registration(active, v, reg_seconds)

    def probe_validator(self, validator, max_time=30):
        with Progress("probing status of {0}".format(validator.name)) as p:
            to = TimeOut(max_time)
            success = False
            while success is False:
                if to():
                    raise ExitError(
                        "{} failed to initialize within {}S.".format(
                            validator.name, to.WaitTime))
                try:
                    success = validator.is_started()
                except Exception as e:
                    print(e.message)
                p.step()
                time.sleep(1)

    def validator_shutdown(self, idx, sig, timeout, force):
        '''
        Dispose of validator subprocesses by index
        Args:
            idx (int): which validator (in self.hdls)
            sig (str): valid values: SIG{TERM,INT,KILL}.
            timeout (int): time to wait in seconds
            force (bool): whether to try SIGKILL if another method has not
                worked within timeout seconds.
        Returns: None
        '''
        assert isinstance(self.hdls[idx], ValidatorManager)
        cfg = self.net_config.get_node_cfg(idx)
        v_name = cfg['NodeName']
        v = self.hdls[idx]
        print('sending %s to %s' % (sig, v_name))
        if v.is_running():
            if sig == 'SIGTERM':
                v.shutdown(term=True)
            elif sig == 'SIGINT':
                v.shutdown()
            elif sig == 'SIGKILL':
                v.shutdown(force=True)
            else:
                raise Exception('unrecognized argument for sig: %s', sig)
        # Would be ideal to move the waiting here into threads in self.commit.
        # Then we could shut down several in parallel, and (besides archive
        # collection, which really should be moved to a provider) self.shutdown
        # would basically just be a numpy.zeros update (re-using this code)!
        to = TimeOut(timeout)
        success = False
        ini = time.time()
        with Progress("giving %s %ss to shutdown: " % (v_name, timeout)) as p:
            while success is False:
                if not v.is_running():
                    success = True
                elif to.is_timed_out():
                    break
                else:
                    time.sleep(1)
                p.step()
        dur = time.time() - ini
        if success is False:
            fail_msg = "%s is still running %.2f seconds after %s"
            fail_msg = fail_msg % (v_name, dur, force)
            if force is False or sig == 'SIGKILL':
                raise ValidatorManagerException(fail_msg)
            else:
                timeout = max(4, timeout)
                print('{}; trying SIGKILL, timeout {}...'
                      .format(fail_msg, timeout))
                self.validator_shutdown(idx, 'SIGKILL', timeout, force)
        if success is True:
            print("%s shut down %.2f seconds after %s" % (v_name, dur, sig))
        self.hdls[idx] = None

    def wait_for_registration(self, validators, validator, max_time=None):
        """
        Wait for newly launched validators to register.
        validators: list of validators on which to wait
        validator: running validator against which to verify registration
        """
        max_time = 120 if max_time is None else max_time
        unregistered_count = len(validators)

        with Progress("{0} waiting for registration of {1} validators".format(
                      validator.name,
                      unregistered_count,
                      )) as p:
            url = validator.url
            to = TimeOut(max_time)

            while unregistered_count > 0:
                if to():
                    raise ExitError(
                        "{} extended validators failed to register "
                        "within {}S.".format(
                            unregistered_count, to.WaitTime))

                p.step()
                time.sleep(1)
                unregistered_count = 0
                for v in validators:
                    if not v.is_registered(url):
                        unregistered_count += 1
                    try:
                        v.check_error()
                    except ValidatorManagerException as vme:
                        v.dump_log()
                        v.dump_stderr()
                        raise ExitError(str(vme))
        return True

    def shutdown(self, archive_name=None):
        vals = [v for v in self.hdls if v is not None]
        if len(vals) > 0:

            with Progress("Sending interrupt signal to validators: ") as p:
                for v in vals:
                    if v.is_running():
                        v.shutdown()
                    p.step()

            running_count = 0
            to = TimeOut(5)
            with Progress("Giving validators time to shutdown: ") as p:
                while True:
                    running_count = 0
                    for v in vals:
                        if v.is_running():
                            running_count += 1
                    if to.is_timed_out() or running_count == 0:
                        break
                    else:
                        time.sleep(1)
                    p.step()

            if running_count != 0:
                with Progress("Killing {} intransigent validators: "
                              .format(running_count)) as p:
                    for v in vals:
                        if v.is_running():
                            v.shutdown(True)
                        p.step()

        if (archive_name is not None
                and self.data_dir is not None
                and os.path.exists(self.data_dir)
                and len(os.listdir(self.data_dir)) > 0):
            tar = tarfile.open('%s.tar.gz' % archive_name, "w|gz")
            base_name = self.get_archive_base_name(archive_name)
            for (dir_path, _, filenames) in walk(self.data_dir):
                for f in filenames:
                    fp = os.path.join(dir_path, f)
                    tar.add(fp, os.path.join(base_name, f))
            tar.close()

    def unpack_blockchain(self, archive_name):
        ext = ["cb", "cs", "gs", "xn"]
        dirs = set()
        tar = tarfile.open(archive_name, "r|gz")
        for f in tar:
            e = f.name[-2:]
            if e in ext or f.name.endswith("wif"):
                base_name = os.path.basename(f.name)
                dest_file = os.path.join(self.data_dir, base_name)
                if os.path.exists(dest_file):
                    os.remove(dest_file)
                tar.extract(f, self.data_dir)
                # extract put the file in a directory below DataDir
                # move the file from extract location to dest_file
                ext_file = os.path.join(self.data_dir, f.name)
                os.rename(ext_file, dest_file)
                # and remember the extract directory for deletion
                dirs.add(os.path.dirname(ext_file))
        tar.close()
        for d in dirs:
            os.rmdir(d)

    @staticmethod
    def get_archive_base_name(path):
        file_name = os.path.basename(path)
        if file_name.endswith(".tar.gz"):
            return file_name[:len(file_name) - 7]
        else:
            return file_name
