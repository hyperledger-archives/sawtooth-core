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
import tarfile

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
        self._files = {}

    def archive(self, archive_name):
        with tarfile.open(archive_name + '.tar', 'w') as archive:
            tempdirs = (os.path.join(self._data_dir, sub)
                        for sub in ['keys', 'data', 'logs'])
            for tempdir in tempdirs:
                for filename in os.listdir(tempdir):
                    target = os.path.join(tempdir, filename)
                    archive.add(target, arcname=filename)

    def clean(self):
        # get a count of nodes still up (and free resources for those now down)
        still_up = [v for v in self._files.keys() if self.is_running(v)]
        if len(still_up) != 0:
            LOGGER.warn('nodes still running: %s', still_up)
        # if all nodes down, and we're responsible for the data dir, delete it
        if self._clean_data_dir is True and len(still_up) == 0:
            if self._data_dir is not None and os.path.isdir(self._data_dir):
                # added safety: make sure the path looks sane
                expected_str = os.path.join(tempfile.tempdir, self._prefix)
                if self._data_dir.startswith(expected_str):
                    shutil.rmtree(self._data_dir)

    def _wrap(self, node_args):
        node_args.currency_home = self._data_dir
        return node_args

    def is_running(self, node_name):
        '''
        In addition to discovering authoritatively whether the node is
        currently running, runs important resource deallocation if it discovers
        a node name is not running but was at one time.  We do this
        deallocation here rather than is stop or kill so that stop and kill can
        be non-blocking.
        Args:
            node_name (str):
        Returns:
        '''
        ret_val = self._controller.is_running(node_name)
        if ret_val is False and node_name in self._files.keys():
            # clean up old file handles
            if self._files[node_name]['StdOut']['Handle'].closed is False:
                self._files[node_name]['StdOut']['Handle'].close()
            if self._files[node_name]['StdErr']['Handle'].closed is False:
                self._files[node_name]['StdErr']['Handle'].close()
            # get rid of vestigial node entry:
            self._files.pop(node_name)
        return ret_val

    def create_genesis_block(self, node_args):
        node_args = self._wrap(node_args)
        self._controller.create_genesis_block(node_args)

    def start(self, node_args):
        '''
        Opens file descriptors for subprocess' stdout and stderr and passes
        these to subprocess.do_start.  It then remembers the file handles for
        when we discover we've lost a node (via a False return from
        'is_running', which is the only real authority on whether or not the
        process is running).  There may be a way to make this polymorphic with
        docker and daemon NodeControllers, but that needs more investigation.
        Args:
            node_args (NodeArguments):
        '''
        if self.is_running(node_args.node_name) is False:
            node_args = self._wrap(node_args)
            node_name = node_args.node_name
            out = os.path.join(self._data_dir, 'logs',
                               '{}.out'.format(node_name))
            out_hdl = open(out, 'a')
            err = os.path.join(self._data_dir, 'logs',
                               '{}.err'.format(node_name))
            err_hdl = open(err, 'a')
            self._controller.do_start(node_args, out_hdl, err_hdl)
            self._files[node_args.node_name] = {
                'StdOut': {'Name': out, 'Handle': out_hdl},
                'StdErr': {'Name': err, 'Handle': err_hdl},
            }

    def stop(self, node_name):
        self._controller.stop(node_name)

    def kill(self, node_name):
        self._controller.kill(node_name)

    def get_node_names(self):
        return self._controller.get_node_names()

    def get_data_dir(self):
        return self._data_dir
