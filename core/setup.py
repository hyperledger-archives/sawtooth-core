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

from setuptools import setup, Extension, find_packages


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
        msg = "setup.py and (bumped?) git describe versions differ: {} != {}"\
            .format(default, parts[0])
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

enclavemod = Extension(
    '_poet_enclave_simulator',
    ['journal/consensus/poet/poet_enclave_simulator/poet_enclave_simulator.i',
     'journal/consensus/poet/poet_enclave_simulator/common.cpp',
     'journal/consensus/poet/poet_enclave_simulator/wait_certificate.cpp',
     'journal/consensus/poet/poet_enclave_simulator/wait_timer.cpp'],
    swig_opts=['-c++'],
    extra_compile_args=extra_compile_args,
    include_dirs=include_dirs,
    libraries=libraries,
    library_dirs=library_dirs)


ecdsamod = Extension('_ECDSARecoverModule',
                     ['gossip/ECDSA/ECDSARecoverModule.i',
                      'gossip/ECDSA/ECDSARecover.cc'],
                     swig_opts=['-c++'],
                     extra_compile_args=extra_compile_args,
                     include_dirs=include_dirs,
                     libraries=libraries,
                     library_dirs=library_dirs)

setup(name='sawtooth-core',
      version=version('0.6.1'),
      description='Intel Labs Distributed ledger testbed',
      author='Mic Bowman, Intel Labs',
      url='http://www.intel.com',
      packages=find_packages(),
      install_requires=['cbor>=0.1.23', 'colorlog', 'pybitcointools',
                        'twisted', 'enum', 'requests'],
      ext_modules=[enclavemod, ecdsamod],
      py_modules=['journal.consensus.poet.poet_enclave_simulator'
                  '.poet_enclave_simulator',
                  'gossip.ECDSA.ECDSARecoverModule'],
      entry_points={
          'console_scripts': [
              'sawtooth = sawtooth.cli:main_wrapper'
          ]
      })

if "clean" in sys.argv and "--all" in sys.argv:
    directory = os.path.dirname(os.path.realpath(__file__))
    for root, fn_dir, files in os.walk(directory):
        for fn in files:
            if fn.endswith(".pyc"):
                os.remove(os.path.join(root, fn))
    for filename in [
            ".coverage",
            "_ECDSARecoverModule.so",
            os.path.join("gossip", "ECDSA", "ECDSARecoverModule.py"),
            os.path.join("gossip", "ECDSA", "ECDSARecoverModule_wrap.cpp"),
            "_poet_enclave_simulator.so",
            os.path.join("journal",
                         "consensus",
                         "poet",
                         "poet_enclave_simulator",
                         "poet_enclave_simulator.py"),
            os.path.join("journal",
                         "consensus",
                         "poet",
                         "poet_enclave_simulator",
                         "_poet_enclave_simulator_wrap.cpp"),
            "nose2-junit.xml"]:
        if os.path.exists(os.path.join(directory, filename)):
            os.remove(os.path.join(directory, filename))
    shutil.rmtree(os.path.join(directory, "build"), ignore_errors=True)
    shutil.rmtree(os.path.join(directory, "htmlcov"), ignore_errors=True)
    shutil.rmtree(os.path.join(directory, "deb_dist"), ignore_errors=True)
    shutil.rmtree(os.path.join(directory, "doc", "code"), ignore_errors=True)
    shutil.rmtree(os.path.join(directory, "doc", "_build"),
                  ignore_errors=True)
    shutil.rmtree(
        os.path.join(directory, "SawtoothLakeLedger.egg-info"),
        ignore_errors=True)
