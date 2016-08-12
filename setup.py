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
from setuptools import setup, find_packages


def bump_version(version):
    (major, minor, patch) = version.split('.')
    patch = str(int(patch) + 1)
    return ".".join([major, minor, patch])


def auto_version(default, strict):
    output = subprocess.check_output(['git', 'describe', '--dirty'])
    parts = output.strip().split('-', 1)
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
        return "-git".join([parts[0], parts[1].replace("-", ".")])
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
        version = default + "-dev1"
    return version


if os.name == 'nt':
    conf_dir = "C:\\Program Files (x86)\\Intel\\sawtooth-validator\\conf"
    log_dir = "C:\\Program Files (x86)\\Intel\\sawtooth-validator\\logs"
    data_dir = "C:\\Program Files (x86)\\Intel\\sawtooth-validator\\data"
    run_dir = "C:\\Program Files (x86)\\Intel\\sawtooth-validator\\run"
else:
    conf_dir = "/etc/sawtooth-validator"
    log_dir = "/var/log/sawtooth-validator"
    data_dir = "/var/lib/sawtooth-validator"
    run_dir = "/var/run/sawtooth-validator"

data_files = [
    (conf_dir, ["etc/txnvalidator.js.example",
                "etc/txnvalidator-logging.js.example",
                "etc/txnvalidator-logging.yaml.example"]),
    (os.path.join(conf_dir, "keys"), []),
    (log_dir, []),
    (data_dir, []),
    (run_dir, [])
]

if os.path.exists("/etc/debian_version"):
    data_files.append(('/etc/init', ['etc/init/sawtooth-validator.conf']))
    data_files.append(('/etc/default', ['etc/default/sawtooth-validator']))

if os.path.exists("/etc/SuSE-release"):
    data_files.append(('/usr/lib/systemd/system',
                       ['etc/systemd/sawtooth-validator.service']))
    data_files.append(('/etc/sysconfig', ['etc/default/sawtooth-validator']))

setup(
    name='sawtooth-validator',
    version=version('1.1.1'),
    description='Validator service for Sawtooth Lake distributed ledger from ',
    author='Mic Bowman, Intel Labs',
    url='http://www.intel.com',
    packages=find_packages(),
    install_requires=['sawtooth-core', 'cbor>=0.1.23', 'colorlog',
                      'twisted', 'PyYAML'],
    data_files=data_files,
    entry_points={
        'console_scripts': [
            'txnkeygen = txnmain.key_gen_cli:main',
            'txnvalidator = txnmain.validator_cli:main_wrapper',
            'txnadmin = txnmain.admin_cli:main'
        ]
    })

if "clean" in sys.argv and "--all" in sys.argv:
    directory = os.path.dirname(os.path.realpath(__file__))
    for root, fn_dir, files in os.walk(directory):
        for fn in files:
            if fn.endswith(".pyc"):
                os.remove(os.path.join(root, fn))
    for filename in [".coverage"]:
        if os.path.exists(os.path.join(directory, filename)):
            os.remove(os.path.join(directory, filename))
    shutil.rmtree(os.path.join(directory, "htmlcov"), ignore_errors=True)
    shutil.rmtree(os.path.join(directory, "deb_dist"), ignore_errors=True)
