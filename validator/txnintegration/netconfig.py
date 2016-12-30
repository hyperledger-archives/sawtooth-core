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

from collections import OrderedDict
import json
import os
import shutil
import tempfile


from sawtooth.validator_config import get_validator_configuration
from txnintegration.matrices import AdjacencyMatrix
from txnintegration.utils import find_or_create_test_key
from txnintegration.utils import generate_private_key
from txnintegration.utils import get_address_from_private_key_wif


class NetworkConfigProvider(object):
    '''
    Helper/shim class for NetworkConfig.  Massages sawtooth's
    get_validator_configuration default validator configurations into formats
    compliant with ValidatorManager, including creating resources if they do
    not exist.
    '''
    def __init__(self, currency_home=None):
        # create space
        self.create_currency_home = False
        self.currency_home = currency_home
        if currency_home is None or not os.path.exists(currency_home):
            self.create_currency_home = True
            self.currency_home = tempfile.mkdtemp()

    def __del__(self):
        self.shutdown()

    def get_massaged_validator_configuration(self):
        '''
        Isolates a work around regarding the environmental variable
        CURRENCYHOME in order to leverage the sawtooth library to produce base
        configs useful for test validators.
        Args:
            currency_home: (str)  directory path for validator related files
        Returns:
            validator_config: (dict)
        '''
        # setup env for get_validator_configuration
        old_currency_home = os.getenv('CURRENCYHOME')
        try:
            os.environ['CURRENCYHOME'] = self.currency_home
            validator_config = get_validator_configuration([], {})
        finally:
            # Restore environmental vars
            if old_currency_home is None:
                os.unsetenv('CURRENCYHOME')
            else:
                os.environ['CURRENCYHOME'] = old_currency_home
        return validator_config

    def flatten_and_rectify_config(self, validator_name, validator_config):
        '''
        Flattens directory hierarchy of validator config for comparability with
        ValidatorManager, and mangles configs produced by get_default_config to
        allow dictionary (rather than config-file) overrides on important
        properties (e.g. NodeName).
        Args:
            validator_name: (str)
            validator_config: (dict)
        Returns:
            config: (dict)  validator config
        '''
        config = validator_config
        dir = self.currency_home
        # flatten for ValidatorManager compatibility
        config['KeyDirectory'] = dir
        config['DataDirectory'] = dir
        config['LogDirectory'] = dir
        config['ConfigDirectory'] = dir
        config['RunDirectory'] = dir
        # rectify get_validator_configuration result and flatten
        config['NodeName'] = validator_name
        config['KeyFile'] = os.path.join(dir, validator_name + '.wif')
        config['PidFile'] = os.path.join(dir, validator_name + '.pid')
        return config

    def provision_validator(self, validator_name):
        '''
        Creates the initial resources and corresponding configuration for a
        test validator conforming to ValidatorManager's flat directory
        structure.
        Args:
            validator_name: (str)
            currency_home: (str)  directory path for validator related files
        Returns:
            config: (dict)  validator configuration
        '''
        config = self.get_massaged_validator_configuration()
        config = self.flatten_and_rectify_config(validator_name, config)
        # provision key, and set derived values
        (_, secret, addr) = find_or_create_test_key(config['KeyFile'])
        config['SigningKey'] = secret
        config['Identifier'] = addr
        return config

    def shutdown(self):
        # don't delete if we did not create
        if self.create_currency_home is True:
            dir = self.currency_home
            if dir is not None:
                exists = False
                try:
                    if os.path.exists(dir):
                        exists = True
                except AttributeError:
                    pass
                if exists is True:
                    shutil.rmtree(dir)


class NetworkConfig(object):
    @staticmethod
    def from_config_list(config_list):
        '''
        Creates a NetworkConfig from an existing list of config files by
        calling the constructor and then replacing the nodes
        Args:
            config_list: (list<dict>)
        Returns:
            net_cfg: (NetworkConfig)

        '''
        net_cfg = NetworkConfig({}, len(config_list))
        net_cfg.nodes = config_list
        return net_cfg

    def __init__(self,
                 n_mag,
                 overrides=None,
                 base_name='validator',
                 base_port=None,
                 base_http_port=None,
                 host=None,
                 endpoint_host=None,
                 provider=None):
        overrides = {} if overrides is None else overrides
        base_port = 9000 if base_port is None else base_port
        base_http_port = 8800 if base_http_port is None else base_http_port
        self.n_mag = n_mag
        self.provider = None
        if provider is not None:
            self.provider = provider
        # set up nodes
        self.nodes = []
        for idx in range(n_mag):
            node_name = "{0}-{1}".format(base_name, idx)
            # get base node configuration
            nd = None
            if self.provider is None:
                nd = OrderedDict()
                nd["NodeName"] = node_name
                key = generate_private_key()
                nd["SigningKey"] = key
                nd["Identifier"] = get_address_from_private_key_wif(key)
            else:
                nd = self.provider.provision_validator(node_name)
            # update basic configuration
            nd.update(overrides)
            nd["id"] = idx
            # ...networking information
            net_info = self.resolve_networking_info(host,
                                                    base_port + idx,
                                                    base_http_port + idx,
                                                    endpoint_host)
            nd.update(net_info)
            nd["Nodes"] = []
            nd["Peers"] = []
            nd["Blacklist"] = []
            # initial athourity
            nd["LedgerURL"] = []
            # aux information
            self.nodes.append(nd)

        self.node_mat = None
        self.peer_mat = None
        self.blacklist_mat = None

    def resolve_networking_info(self, host, udp, http, endpoint):
        ret = {}
        ret['Host'] = 'localhost' if host is None else host
        ret["Port"] = udp
        ret["HttpPort"] = http
        ret['Listen'] = [
            '%s:%s/UDP gossip' % (ret['Host'], udp),
            '%s:%s/TCP http' % (ret['Host'], http),
        ]
        if endpoint is not None:
            ret['Endpoint'] = {
                "Host": endpoint,
                "Port": udp,
                "HttpPort": http,
            }
        return ret

    def set_ledger_url(self, node_index, ledger_node_indexes):
        self.nodes[node_index]['LedgerURL'] = [
            'http://%s:%s' % (nd['Host'], nd['HttpPort'])
            for (idx, nd) in enumerate(self.nodes)
            if idx in ledger_node_indexes
        ]

    def _get_gossip_info(self, idx):
        nd = self.nodes[idx]
        return {
            "NodeName": nd["NodeName"],
            "Identifier": nd["Identifier"],
            "Host": nd["Host"],
            "Port": nd["Port"],
            "HttpPort": nd["HttpPort"],
        }

    def set_nodes(self, node_mat):
        if self.node_mat is not None:
            raise Exception('validator configuration is static')
        self.node_mat = AdjacencyMatrix(self.n_mag, node_mat)
        mat = self.node_mat.get_mat()
        for (this_idx, this) in enumerate(self.nodes):
            this['Nodes'] = []
            for (other_idx, add_other) in enumerate(mat[this_idx]):
                if add_other == 1:
                    this['Nodes'].append(self._get_gossip_info(other_idx))

    def set_peers(self, peer_mat):
        if self.peer_mat is not None:
            raise Exception('validator configuration is static')
        self.peer_mat = AdjacencyMatrix(self.n_mag, peer_mat)
        mat = self.peer_mat.get_mat()
        for (nd_idx, nd) in enumerate(self.nodes):
            nd['Peers'] = []
            for (peer_idx, is_peer) in enumerate(mat[nd_idx]):
                if is_peer == 1 and peer_idx != nd_idx:
                    nd['Peers'].append(self.nodes[peer_idx]['NodeName'])

    def set_blacklist(self, blacklist_mat=None):
        if self.blacklist_mat is not None:
            raise Exception('validator configuration is static')
        if blacklist_mat is None:
            assert self.peer_mat is not None
            blacklist_mat = self.peer_mat.negate()
        self.blacklist_mat = AdjacencyMatrix(self.n_mag, blacklist_mat)
        mat = self.blacklist_mat.get_mat()
        for (nd_idx, nd) in enumerate(self.nodes):
            nd['Blacklist'] = []
            for (exclude_idx, is_exclude) in enumerate(mat[nd_idx]):
                if is_exclude == 1:
                    exclude = self._get_gossip_info(exclude_idx)
                    nd['Blacklist'].append(exclude['Identifier'])

    def get_node_cfg(self, idx):
        ret = self.nodes[idx].copy()
        return ret

    def set_node_cfg(self, idx, cfg):
        self.nodes[idx] = cfg.copy()

    def write_node_cfg(self, idx, file_name=None):
        cfg = self.get_node_cfg(idx)
        if file_name is None:
            dir = cfg['ConfigDirectory']
            file_name = cfg['NodeName'] + '.json'
            file_name = os.path.join(dir, file_name)
        with open(file_name, 'w') as f:
            f.write(json.dumps(cfg, indent=4) + '\n')
        return file_name

    def get_config_list(self):
        return [self.get_node_cfg(i) for i in range(self.n_mag)]

    def print_config_list(self):
        val = self.get_config_list()
        print(json.dumps(val, indent=4))


def get_default_network_config_obj(num_nodes,
                                   overrides=None,
                                   data_dir=None,
                                   block_chain_archive=None,
                                   http_port=None,
                                   udp_port=None,
                                   host=None,
                                   endpoint_host=None):
    '''
    Factory to generate NetworkConfig objects for common cases.
    Args:
        num_nodes (int): network size
        overrides (dict): config overrides for network
        data_dir (str): data directory for validator files/logs etc
        block_chain_archive (str): previous, saved data directory to unpack
        http_port (int): base http port for network
        udp_port (int): base udp port for network
        host (str): host name or address
        endpoint_host (str): endpoint host name or address
    Returns:
        net_cfg (NetworkConfig)
    '''
    if block_chain_archive is not None:
        raise NotImplementedError("'RepeatProvider' under construction")
    ncp = NetworkConfigProvider(currency_home=data_dir)
    net_cfg = NetworkConfig(num_nodes,
                            overrides=overrides,
                            base_http_port=http_port,
                            base_port=udp_port,
                            host=host,
                            endpoint_host=endpoint_host,
                            provider=ncp)
    for i in range(1, len(net_cfg.nodes)):
        net_cfg.set_ledger_url(i, [0])
    return net_cfg
