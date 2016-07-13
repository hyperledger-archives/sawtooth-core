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
import sys
import tarfile
import tempfile
import time
import os
from os import walk

import pybitcointools

from txnintegration.exceptions import ExitError
from txnintegration.exceptions import ValidatorManagerException
from txnintegration.utils import find_txn_validator
from txnintegration.utils import Progress
from txnintegration.utils import TimeOut
from txnintegration.validator_manager import ValidatorManager

defaultValidatorConfig = {u'CertificateSampleLength': 5,
                          u'InitialWaitTime': 25.0,
                          u'LedgerType': u'lottery',
                          u'MaxTransactionsPerBlock': 1000,
                          u'MinTransactionsPerBlock': 1,
                          u'MinimumWaitTime': 1.0,
                          u'NetworkBurstRate': 128000,
                          u'NetworkDelayRange': [0.0, 0.1],
                          u'NetworkFlowRate': 96000,
                          u'Restore': False,
                          u'TargetConnectivity': 3,
                          u'TargetWaitTime': 5.0,
                          u'TopologyAlgorithm': u'RandomWalk',
                          u'TransactionFamilies': [
                              u'ledger.transaction.integer_key'],
                          u'UseFixedDelay': True,
                          u'Profile': True}


class ValidatorNetworkManager(object):
    class AdminNode(object):
        SigningKey = None
        Address = None

        def __init__(self):
            self.SigningKey = pybitcointools.random_key()
            self.Address = pybitcointools.privtoaddr(self.SigningKey)

    def __init__(self,
                 txnvalidator=None,
                 cfg=None,
                 dataDir=None,
                 httpPort=8800,
                 udpPort=8900,
                 blockChainArchive=None,
                 log_config=None,
                 staticNetwork=None,
                 ):

        self.staticNetwork = staticNetwork
        self.Validators = []
        self.ValidatorMap = {}
        self.ValidatorConfig = None

        self.NextValidatorId = 0
        self.HttpPortBase = httpPort
        self.UdpPortBase = udpPort

        if cfg is None:
            cfg = defaultValidatorConfig
        self.ValidatorConfig = cfg
        self.validator_log_config = log_config

        if txnvalidator is None:
            txnvalidator = find_txn_validator()
        self.txnvalidator = txnvalidator

        self.tempDataDir = False
        if dataDir is None:
            self.tempDataDir = True
            dataDir = tempfile.mkdtemp()
        self.DataDir = dataDir

        self.blockChainArchive = blockChainArchive
        if blockChainArchive is not None:
            if not os.path.isfile(blockChainArchive):
                raise ExitError("Block chain archive to load {} does not "
                                "exist.".format(blockChainArchive))
            else:
                self.unpack_blockchain(blockChainArchive)

        self.AdminNode = ValidatorNetworkManager.AdminNode()

        self.ValidatorConfig['DataDirectory'] = self.DataDir
        self.ValidatorConfig['Host'] = "localhost"
        self.ValidatorConfig["AdministrationNode"] = self.AdminNode.Address
        self.ValidatorConfig['Restore'] = False

    def __del__(self):
        if self.tempDataDir:
            if os.path.exists(self.DataDir):
                shutil.rmtree(self.DataDir)

    def validator(self, idx):
        v = None
        try:
            if idx in self.ValidatorMap:
                v = self.ValidatorMap[idx]
            else:
                idx = int(idx)
                if idx in self.ValidatorMap:
                    v = self.ValidatorMap[idx]
        except:
            print sys.exc_info()[0]

        return v

    def staged_launch_network(self, count=1, stage1max=12, increment=12):
        validators = []

        if count <= stage1max:
            validators = self.launch_network(count)
            print "Launch complete with {0} validators launched" \
                .format(len(self.Validators))
            return validators
        else:
            validators = self.launch_network(stage1max)
            print "Staged launch initiated with {0} validators launched" \
                .format(len(self.Validators))
            staged_validators = self.staged_expand_network(count - stage1max)
            validators += staged_validators

            return validators

    def staged_expand_network(self, count=1, increment=12):
        validators = []
        remaining_to_launch = count
        while remaining_to_launch > 0:
            number_to_launch = \
                min([remaining_to_launch, increment, len(self.Validators)])
            validators_to_use = \
                self.Validators[len(self.Validators) - number_to_launch:]
            print "Staged launching {0} validators".format(number_to_launch)
            stagedvals = self.expand_network(validators_to_use, 1)
            remaining_to_launch -= number_to_launch
            validators += stagedvals

        return validators

    def launch_network(self, count=1, others_daemon=False):
        validators = []

        with Progress("Launching initial validator") as p:
            cfg = {
                'LedgerURL': "**none**",
                'Restore': self.blockChainArchive,
            }
            validator = self.launch_node(overrides=cfg,
                                         genesis=True,
                                         daemon=False)
            validators.append(validator)
            probe_func = validator.is_registered
            if self.ValidatorConfig.get('LedgerType', '') == 'quorum':
                probe_func = validator.is_started
            while not probe_func():
                try:
                    validator.check_error()
                except ValidatorManagerException as vme:
                    validator.dump_log()
                    validator.dump_stderr()
                    raise ExitError(str(vme))
                p.step()
                time.sleep(1)

        with Progress("Launching validator network") as p:
            cfg = {
                'LedgerURL': validator.Url,
                'Restore': self.blockChainArchive,
            }
            for _ in range(1, count):
                v = self.launch_node(overrides=cfg,
                                     genesis=False,
                                     daemon=others_daemon)
                validators.append(v)
                p.step()

        self.wait_for_registration(validators, validator)

        return validators

    def launch_node(self,
                    overrides=None,
                    launch=True,
                    genesis=False,
                    daemon=False,
                    delay=False):
        id = self.NextValidatorId
        self.NextValidatorId += 1
        cfg = self.ValidatorConfig.copy()
        if overrides:
            cfg.update(overrides)
        cfg['id'] = id
        cfg['NodeName'] = "validator-{}".format(id)
        cfg['HttpPort'] = self.HttpPortBase + id
        cfg['Port'] = self.UdpPortBase + id
        staticNode = False
        if self.staticNetwork is not None:
            assert 'Nodes' in cfg.keys()
            staticNode = True
            nd = self.staticNetwork.get_node(id)
            q = self.staticNetwork.get_quorum(id, dfl=cfg.get('Quorum', []))
            cfg['NodeName'] = nd['ShortName']
            cfg['HttpPort'] = nd['HttpPort']
            cfg['Port'] = nd['Port']
            cfg['SigningKey'] = self.staticNetwork.get_key(id)
            cfg['Identifier'] = nd['Identifier']
            cfg['Quorum'] = q
        log_config = self.validator_log_config.copy() \
            if self.validator_log_config \
            else None

        v = ValidatorManager(self.txnvalidator, cfg, self.DataDir,
                             self.AdminNode, log_config, staticNode=staticNode)
        v.launch(launch, genesis=genesis, daemon=daemon, delay=delay)
        self.Validators.append(v)
        self.ValidatorMap[id] = v
        self.ValidatorMap[cfg['NodeName']] = v
        return v

    def wait_for_registration(self, validators, validator, max_time=120):
        """
        Wait for newly launched validators to register.
        validators: list of validators on which to wait
        validator: running validator against which to verify registration
        """
        unregCount = len(validators)

        with Progress("Waiting for registration of {0} validators".format(
                unregCount)) as p:
            url = validator.Url
            to = TimeOut(max_time)

            while unregCount > 0:
                if to():
                    raise ExitError(
                        "{} extended validators failed to register "
                        "within {}S.".format(
                            unregCount, to.WaitTime))

                p.step()
                time.sleep(1)
                unregCount = 0
                for v in validators:
                    if not v.is_registered(url):
                        unregCount += 1
                    try:
                        v.check_error()
                    except ValidatorManagerException as vme:
                        v.dump_log()
                        v.dump_stderr()
                        raise ExitError(str(vme))

    def expand_network(self, validators, count=1):
        """
        expand existing network.
        validators: running validators against which to launch new nodes
        count: new validators to launch against each running validator
        validator: running validator against which to verify registration
        """
        ledger_validator = validators[0]
        new_validators = []

        with Progress("Extending validator network") as p:
            cfg = {
                'LedgerURL': ledger_validator.Url
            }
            for _ in validators:
                for _ in range(0, count):
                    v = self.launch_node(overrides=cfg)
                    new_validators.append(v)
                    p.step()

        self.wait_for_registration(new_validators,
                                   ledger_validator,
                                   max_time=240)

        return new_validators

    def shutdown(self):
        if len(self.Validators) == 0:
            # no validators to shutdown
            return

        with Progress("Sending interrupt signal to validators: ") as p:
            for v in self.Validators:
                if v.is_running():
                    v.shutdown()
                p.step()

        running_count = 0
        to = TimeOut(10)
        with Progress("Giving validators time to shutdown: ") as p:
            while True:
                running_count = 0
                for v in self.Validators:
                    if v.is_running():
                        running_count = running_count + 1
                if to.is_timed_out() or running_count == 0:
                    break
                else:
                    time.sleep(1)
                p.step()

        if running_count != 0:
            with Progress("Killing {} intransigent validators: "
                          .format(running_count)) as p:
                for v in self.Validators:
                    if v.is_running():
                        v.shutdown(True)
                    p.step()

        # wait for windows to learn that the subprocess are dead.
        if os.name == "nt":
            time.sleep(5)

    def status(self):
        out = []
        for v in self.Validators:
            out.append(v.status())
        return out

    def urls(self):
        out = []
        for v in self.Validators:
            out.append(v.Url)
        return out

    def create_result_archive(self, archive_name):
        if self.DataDir is not None \
                and os.path.exists(self.DataDir) \
                and len(self.Validators) != 0:
            tar = tarfile.open(archive_name, "w|gz")
            base_name = self.get_archive_base_name(archive_name)
            for (dirpath, _, filenames) in walk(self.DataDir):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    tar.add(fp, os.path.join(base_name, f))
            tar.close()
            return True
        return False

    def unpack_blockchain(self, archive_name):
        ext = ["cb", "cs", "gs", "xn"]
        dirs = set()
        tar = tarfile.open(archive_name, "r|gz")
        for f in tar:
            e = f.name[-2:]
            if e in ext or f.name.endswith("wif"):
                base_name = os.path.basename(f.name)
                dest_file = os.path.join(self.DataDir, base_name)
                if os.path.exists(dest_file):
                    os.remove(dest_file)
                tar.extract(f, self.DataDir)
                # extract put the file in a directory below DataDir
                # move the file from extract location to dest_file
                ext_file = os.path.join(self.DataDir, f.name)
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
