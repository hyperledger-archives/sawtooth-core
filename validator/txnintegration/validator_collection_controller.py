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

import shutil
import tarfile
import tempfile
import time
import os
from os import walk

import pybitcointools

from txnintegration.exceptions import ExitError
from txnintegration.exceptions import ValidatorManagerException
from txnintegration.matrices import NodeController
from txnintegration.utils import find_txn_validator
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
            self.SigningKey = pybitcointools.random_key()
            self.Address = pybitcointools.privtoaddr(self.SigningKey)

    def __init__(self,
                 net_config,
                 txnvalidator=None,
                 data_dir=None,
                 endpoint_host=None,
                 block_chain_archive=None,
                 log_config=None,
                 ):
        super(ValidatorCollectionController, self).__init__(net_config.n_mag)
        self._validators = [[None, x] for x in net_config.get_config_list()]

        if txnvalidator is None:
            txnvalidator = find_txn_validator()
        self.txnvalidator = txnvalidator

        self._endpoint_host = endpoint_host

        self.validator_log_config = log_config

        self.temp_data_dir = False
        if data_dir is None:
            self.temp_data_dir = True
            data_dir = tempfile.mkdtemp()
        self.data_dir = data_dir

        self.block_chain_archive = block_chain_archive
        if block_chain_archive is not None:
            if not os.path.isfile(block_chain_archive):
                raise ExitError("Block chain archive to load {} does not "
                                "exist.".format(block_chain_archive))
            else:
                self.unpack_blockchain(block_chain_archive)

        self.admin_node = ValidatorCollectionController.AdminNode()

    def __del__(self):
        if self.temp_data_dir:
            if os.path.exists(self.data_dir):
                shutil.rmtree(self.data_dir)

    def set_validator_configuration(self, idx, cfg):
        v = self.validator(idx)
        if v in self.active_validators():
            raise ValidatorManagerException('%s is running' % (v.name))
        self._validators[idx][1] = cfg

    def validator(self, idx):
        return self._validators[idx][0]

    def configuration(self, idx):
        return self._validators[idx][1]

    def active_validators(self):
        return [v for [v, _] in self._validators if v is not None]

    def status(self):
        return [v.status() for v in self.active_validators()]

    def urls(self):
        return [v.url for v in self.active_validators()]

    def activate(self, idx,
                 probe_seconds=30,
                 launch=True,
                 daemon=False,
                 delay=False,
                 **kwargs
                 ):
        [sta, cfg] = self._validators[idx]
        assert sta is None
        cfg['DataDirectory'] = self.data_dir
        cfg["AdministrationNode"] = self.admin_node.Address
        cfg['Restore'] = False
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
        print 'launching %s...' % (v.name),
        v.launch(launch, daemon=daemon, delay=delay)
        if probe_seconds > 0:
            self.probe_validator(v, max_time=probe_seconds)
        else:
            print
        self._validators[idx][0] = v
        return v

    def deactivate(self, idx, **kwargs):
        v = self._validators[idx][0]
        assert isinstance(v, ValidatorManager)
        self._validators[idx][0] = None
        v.shutdown()

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
                    success = validator.is_ready()
                except Exception as e:
                    print e.message
                p.step()
                time.sleep(1)

    def launch_node(self, idx,
                    launch=True,
                    daemon=False,
                    delay=False,
                    ):
        cfg = self.config_list[idx]
        cfg['DataDirectory'] = self.data_dir
        cfg["AdministrationNode"] = self.admin_node.address
        cfg['Restore'] = False
        log_config = self.validator_log_config
        if log_config is not None:
            log_config = self.validator_log_config.copy()
        v = ValidatorManager(self.txnvalidator,
                             cfg,
                             self.data_dir,
                             self.admin_node,
                             log_config,
                             )
        v.launch(launch, daemon=daemon, delay=delay)
        self._validators.append(v)
        return v

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
        self._validators = [v for [v, _] in self._validators if v is not None]
        if len(self._validators) == 0:
            # no validators to shutdown
            return
        with Progress("Sending interrupt signal to validators: ") as p:
            for v in self._validators:
                if v.is_running():
                    v.shutdown()
                p.step()
        running_count = 0
        to = TimeOut(1)
        with Progress("Giving validators time to shutdown: ") as p:
            while True:
                running_count = 0
                for v in self._validators:
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
                for v in self._validators:
                    if v.is_running():
                        v.shutdown(True)
                    p.step()
        if (archive_name is not None
                and self.data_dir is not None
                and os.path.exists(self.data_dir)
                and len(self._validators) != 0):
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
