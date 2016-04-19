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

import glob
import shutil
import sys
import tarfile
import tempfile
import time
import os
from os import walk

import pybitcointools

from txnintegration.utils import ExitError
from txnintegration.utils import find_txn_validator
from txnintegration.utils import Progress
from txnintegration.utils import TimeOut
from txnintegration.validator_manager import ValidatorManager

defaultValidatorConfig = {u'CertificateSampleLength': 5,
                          u'InitialWaitTime': 25.0,
                          u'LedgerType': u'lottery',
                          u'LogLevel': u'WARNING',
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
                          u'UseFixedDelay': True}


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
                 blockChainArchive=None):

        self.Validators = []
        self.ValidatorMap = {}
        self.ValidatorConfig = None

        self.NextValidatorId = 0
        self.HttpPortBase = httpPort
        self.UdpPortBase = udpPort

        if cfg is None:
            cfg = defaultValidatorConfig
        self.ValidatorConfig = cfg

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

    def launch_network(self, count=1):
        with Progress("Launching initial validator") as p:
            self.ValidatorConfig['LedgerURL'] = "**none**"
            self.ValidatorConfig['GenesisLedger'] = True
            if self.blockChainArchive is not None:
                self.ValidatorConfig['Restore'] = True

            validator = self.launch_node()
            while not validator.is_registered():
                if validator.has_error():
                    validator.dump_log()
                    validator.dump_stderr()
                    raise ExitError("Initial validator crashed.")
                p.step()
                time.sleep(1)

        with Progress("Launching validator network") as p:
            self.ValidatorConfig['LedgerURL'] = validator.Url
            self.ValidatorConfig['GenesisLedger'] = False
            self.ValidatorConfig['Restore'] = False
            for _ in range(1, count):
                self.launch_node()
                p.step()

        with Progress("Waiting for validator registration") as p:
            unregCount = len(self.Validators)
            url = validator.Url
            to = TimeOut(120)

            while unregCount > 0:
                if to():
                    raise ExitError(
                        "{} validators failed to register within {}S.".format(
                            unregCount, to.WaitTime))

                p.step()
                time.sleep(1)
                unregCount = 0
                for v in self.Validators:
                    if not v.is_registered(url):
                        unregCount += 1
                    if v.has_error():
                        v.dump_log()
                        v.dump_stderr()
                        raise ExitError(
                            "{} crashed during initialization.".format(v.Name))

    def launch_node(self, launch=True):
        id = self.NextValidatorId
        self.NextValidatorId += 1
        cfg = self.ValidatorConfig.copy()
        cfg['id'] = id
        cfg['NodeName'] = "validator-{}".format(id)
        cfg['HttpPort'] = self.HttpPortBase + id
        cfg['Port'] = self.UdpPortBase + id

        v = ValidatorManager(self.txnvalidator, cfg, self.DataDir,
                             self.AdminNode)
        v.launch(launch)
        self.Validators.append(v)
        self.ValidatorMap[id] = v
        self.ValidatorMap[cfg['NodeName']] = v
        return v

    def shutdown(self):
        if len(self.Validators) == 0:
            # no validators to shutdown
            return

        with Progress("Sending shutdown message to validators: ") as p:
            for v in self.Validators:
                if v.is_running():
                    v.post_shutdown()
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

    def create_result_archive(self, archiveName):
        if self.DataDir is not None \
                and os.path.exists(self.DataDir) \
                and len(self.Validators) != 0:
            tar = tarfile.open(archiveName, "w|gz")
            for (dirpath, _, filenames) in walk(self.DataDir):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    tar.add(fp, f)
            tar.close()
            return True
        return False

    def pack_blockchain(self, archiveName):
        tar = tarfile.open(archiveName, "w|gz")
        fp = os.path.join(self.DataDir, self.Validators[0].Name + "_*")
        for f in glob.glob(fp):
            tar.add(f, os.path.basename(f))
        fp = os.path.join(self.DataDir, "*.wif")
        for f in glob.glob(fp):
            tar.add(f, os.path.basename(f))
        tar.close()

    def unpack_blockchain(self, archiveName):
        # only unpack the root validator data, this
        # allows us to use Result archives from failed tests as input
        # blockchains
        tar = tarfile.open(archiveName, "r|gz")
        for f in tar:
            if f.name.startswith("validator-0_")  \
                    or f.name.endswith("wif"):
                tar.extract(f, self.DataDir)
        tar.close()
