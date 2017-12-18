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

import os
import subprocess

from setuptools import setup, find_packages


data_files = []

if os.path.exists("/etc/default"):
    data_files.append(
        ('/etc/default',
         ['packaging/systemd/sawtooth-poet-validator-registry-tp']))

if os.path.exists("/lib/systemd/system"):
    data_files.append(
        ('/lib/systemd/system',
         ['packaging/systemd/sawtooth-poet-validator-registry-tp.service']))


setup(
    name='sawtooth-poet-families',
    version=subprocess.check_output(
        ['../../../bin/get_version']).decode('utf-8').strip(),
    description='Sawtooth Transaction Processor Families',
    author='Hyperledger Sawtooth',
    url='https://github.com/hyperledger/sawtooth-core',
    packages=find_packages(),
    install_requires=[
        'colorlog',
        'cryptography>=1.7.1',
        'sawtooth-poet-common',
        'sawtooth-sdk',
        'sawtooth-signing',
    ],
    data_files=data_files,
    entry_points={
        'console_scripts': [
            'poet-validator-registry-tp = sawtooth_validator_registry.validator_registry.processor.main:main'
        ]
    })
