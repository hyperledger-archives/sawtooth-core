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

import random
import string
import hashlib
import os

import sawtooth_signing as signing


def random_name(length=16):
    return ''.join(
        random.SystemRandom().choice(string.ascii_uppercase + string.digits)
        for _ in range(length))


def create_random_private_key():
    return signing.generate_privkey()


def create_random_public_key():
    return signing.generate_pubkey(create_random_private_key())


def create_random_public_key_hash():
    return \
        hashlib.sha256(create_random_public_key().encode()).hexdigest()
