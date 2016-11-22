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
import logging
import os
import shutil
import tempfile

from sawtooth.manage.node import NodeController

LOGGER = logging.getLogger(__name__)


class WrappedNodeController(NodeController):
    def __init__(self, controller, data_dir=None, clean_data_dir=None):
        self._prefix = 'node_ctrl_'
        self._controller = controller
        self._clean_data_dir = clean_data_dir
        self._data_dir = data_dir
        if self._data_dir is None:
            self._data_dir = tempfile.mkdtemp(prefix=self._prefix)
            self._clean_data_dir = True
        elif not os.path.isdir(self._data_dir):
            os.makedirs(self._data_dir)
        for x in ['keys', 'data', 'logs', 'etc', 'run']:
            sub_dir = '{}/{}'.format(self._data_dir, x)
            if not os.path.isdir(sub_dir):
                os.makedirs(sub_dir)

    def clean(self):
        if self._clean_data_dir is True:
            if self._data_dir is not None and os.path.isdir(self._data_dir):
                # added safety: make sure the path looks sane
                expected_str = os.path.join(tempfile.tempdir, self._prefix)
                if self._data_dir.startswith(expected_str):
                    shutil.rmtree(self._data_dir)

    def _wrap(self, node_args):
        node_args.currency_home = self._data_dir
        return node_args

    def is_running(self, node_name):
        return self._controller.is_running(node_name)

    def create_genesis_block(self, node_args):
        node_args = self._wrap(node_args)
        self._controller.create_genesis_block(node_args)

    def start(self, node_args):
        node_args = self._wrap(node_args)
        self._controller.start(node_args)

    def stop(self, node_name):
        self._controller.stop(node_name)

    def kill(self, node_name):
        self._controller.kill(node_name)

    def get_node_names(self):
        return self._controller.get_node_names()

    def get_data_dir(self):
        return self._data_dir
