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
import hashlib
import random
import string
from journal.consensus.poet0.poet_enclave_simulator \
    import poet_enclave_simulator as pe_sim


class AttrDict(dict):
    """ A simple mocking class.
     """
    def __init__(self, **kwargs):
        dict.__init__(self, *(), **kwargs)

    def __getattr__(self, name):
        return self[name]


def generate_certs(count):
    out = []
    for i in range(0, count):
        out.append(AttrDict(**{
            "identifier": random_name(pe_sim.IDENTIFIER_LENGTH),
            "duration": 2,
            "local_mean": 1
        }))
    return out


def random_name(length=16):
    return ''.join(
        random.SystemRandom().choice(string.ascii_uppercase + string.digits)
        for _ in range(length))


def generate_txn_ids(count):
    out = []
    hasher = hashlib.sha256()
    for i in range(0, count):
        name = random_name(pe_sim.IDENTIFIER_LENGTH)
        hasher.update(name)
        out.append(name)
    return out, hasher.hexdigest()
