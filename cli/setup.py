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

from __future__ import print_function

import subprocess

from setuptools import setup, find_packages

conf_dir = "/etc/sawtooth"

data_files = [
    (conf_dir, ['cli.toml.example'])
]

setup(
    name='sawtooth-cli',
    version=subprocess.check_output(
        ['../bin/get_version']).decode('utf-8').strip(),
    description='Sawtooth CLI',
    author='Hyperledger Sawtooth',
    url='https://github.com/hyperledger/sawtooth-core',
    packages=find_packages(),
    install_requires=[
        'colorlog', 'protobuf', 'sawtooth-signing', 'toml', 'PyYAML',
        'requests'
    ],
    data_files=data_files,
    entry_points={
        'console_scripts': [
            'sawadm = sawtooth_cli.sawadm:main_wrapper',
            'sawnet = sawtooth_cli.sawnet:main_wrapper',
            'sawset = sawtooth_cli.sawset:main_wrapper',
            'sawtooth = sawtooth_cli.main:main_wrapper'
        ]
    })
