# Copyright 2016, 2017 Intel Corporation
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
    conf_dir = "C:\\Program Files (x86)\\Intel\\sawtooth\\conf"
    log_dir = "C:\\Program Files (x86)\\Intel\\sawtooth\\logs"
    data_dir = "C:\\Program Files (x86)\\Intel\\sawtooth\\data"
else:
    conf_dir = "/etc/sawtooth"
    log_dir = "/var/log/sawtooth"
    data_dir = "/var/lib/sawtooth"

data_files = [
    (conf_dir, ['etc/path.toml.example']),
    (os.path.join(conf_dir, "keys"), []),
    (log_dir, []),
    (data_dir, [])
]

if os.path.exists("/etc/default"):
    data_files.append(('/etc/default', ['etc/default/sawtooth-validator']))

if os.path.exists("/lib/systemd/system"):
    data_files.append(('/lib/systemd/system',
                       ['etc/systemd/sawtooth-validator.service']))

setup(
    name='sawtooth-validator',
    version=version('0.8.1'),
    description='Sawtooth Lake Validator',
    author='Intel Corporation',
    url='https://github.com/hyperledger/sawtooth-core',
    packages=find_packages(),
    install_requires=[
        "cbor>=0.1.23",
        "colorlog",
        "protobuf",
        "lmdb",
        "requests",
        "sawtooth-signing",
        "toml",
        "pyzmq",
    ],
    data_files=data_files,
    entry_points={
        'console_scripts': [
            'validator = sawtooth_validator.server.cli:main'
        ]
    })
