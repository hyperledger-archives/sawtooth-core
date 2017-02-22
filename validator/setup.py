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

import os
import shutil
import subprocess
import sys

# from distutils.core import setup, Extension, find_packages
from setuptools import setup, Extension, find_packages


def bump_version(version):
    (major, minor, patch) = version.split('.')
    patch = str(int(patch) + 1)
    return ".".join([major, minor, patch])


def auto_version(default, strict):
    output = subprocess.check_output(['git', 'describe', '--dirty'])
    parts = output.decode('utf-8').strip().split('-', 1)
    parts[0] = parts[0][1:]  # strip the leading 'v'
    if len(parts) == 2:
        parts[0] = bump_version(parts[0])
    if default != parts[0]:
        msg = "setup.py and (bumped?) git describe versions differ: " \
              "{} != {}".format(default, parts[0])
        if strict:
            print >> sys.stderr, "ERROR: " + msg
            sys.exit(1)
        else:
            print >> sys.stderr, "WARNING: " + msg
            print >> sys.stderr, "WARNING: using setup.py version {}".format(
                default)
            parts[0] = default

    if len(parts) == 2:
        return ".git".join([parts[0], parts[1].replace("-", ".")])
    else:
        return parts[0]


def version(default):
    if 'VERSION' in os.environ:
        if os.environ['VERSION'] == 'AUTO_STRICT':
            version = auto_version(default, strict=True)
        elif os.environ['VERSION'] == 'AUTO':
            version = auto_version(default, strict=False)
        else:
            version = os.environ['VERSION']
    else:
        version = default + ".dev1"
    return version


if os.name == 'nt':
    extra_compile_args = ['/EHsc']
    libraries = ['json-c', 'cryptopp-static']
    include_dirs = ['deps/include', 'deps/include/cryptopp']
    library_dirs = ['deps/lib']
elif sys.platform == 'darwin':
    os.environ["CC"] = "clang++"
    extra_compile_args = ['-std=c++11']
    libraries = ['json-c', 'cryptopp']
    include_dirs = ['/usr/local/include']
    library_dirs = ['/usr/local/lib']
else:
    extra_compile_args = ['-std=c++11']
    libraries = ['json-c', 'cryptopp']
    include_dirs = []
    library_dirs = []

if os.name == 'nt':
    conf_dir = "C:\\Program Files (x86)\\Intel\\sawtooth-validator\\conf"
    log_dir = "C:\\Program Files (x86)\\Intel\\sawtooth-validator\\logs"
    data_dir = "C:\\Program Files (x86)\\Intel\\sawtooth-validator\\data"
    run_dir = "C:\\Program Files (x86)\\Intel\\sawtooth-validator\\run"
    static_content_dir = "Lib\\site-packages\\txnserver\\static_content"
else:
    conf_dir = "/etc/sawtooth-validator"
    log_dir = "/var/log/sawtooth-validator"
    data_dir = "/var/lib/sawtooth-validator"
    run_dir = "/var/run/sawtooth-validator"
    static_content_dir = "lib/python2.7/dist-packages/txnserver/static_content"


# collect the static files to put in the installation dir
static_content_files = []
for root, dirs, files in os.walk("txnserver/static_content"):
    for file in files:
        static_content_files.append(os.path.join(root, file))


data_files = [
    (conf_dir, ["etc/txnvalidator-logging.yaml.example"]),
    (os.path.join(conf_dir, "keys"), []),
    (log_dir, []),
    (data_dir, []),
    (run_dir, []),
    (static_content_dir, static_content_files),
]

if os.path.exists("/etc/default"):
    data_files.append(('/etc/default', ['etc/default/sawtooth-validator']))

if os.path.exists("/lib/systemd/system"):
    data_files.append(('/lib/systemd/system',
                       ['etc/systemd/sawtooth-validator.service']))

setup(
    name='sawtooth-validator',
    version=version('0.8.1'),
    description='Validator service for Sawtooth Lake distributed ledger from ',
    author='Mic Bowman, Intel Labs',
    url='http://www.intel.com',
    packages=find_packages(),
    install_requires=[
        'sawtooth-signing',
        'cbor>=0.1.23',
        'colorlog',
        'PyYAML',
        'protobuf',
        'requests',
        'pyzmq'
        ],
    data_files=data_files,
    entry_points={
        'console_scripts': [
            'txnvalidator = txnserver.validator_cli:main_wrapper'
        ]
    })
