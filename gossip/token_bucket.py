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
"""
This module implements the TokenBucket class for managing the average
rate of data transmission between nodes.
"""

import logging

import time

logger = logging.getLogger(__name__)


class TokenBucket(object):
    """The TokenBucket class allows for traffic shaping via an average
    transmission rate (the drip rate) and a limit to 'burstiness' (via
    the bucket capacity).

    Attributes:
        DefaultDripRate (int): The default number of tokens which are
           added to the bucket per second.
        DefaultCapacity (int): The default maximum number of tokens
           which can fit in the bucket.
        DripRate (int): The configured number of tokens added to the
           bucket per second.
        Capacity (int): The configured maximum number of tokens which
           can fit in the bucket.
        LastDrip (float): The time in seconds since the epoch.
        Tokens (int): The number of tokens in the bucket.

    """
    DefaultDripRate = 32000
    DefaultCapacity = DefaultDripRate * 2

    def __init__(self, rate=None, capacity=None):
        """Constructor for the TokenBucket class.

        Args:
            rate (int): the drip rate for the newly created bucket in
                tokens per second.
            capacity (int): the maximum number of tokens the newly
                created bucket can hold.

        """
        self.DripRate = rate or self.DefaultDripRate
        self.Capacity = capacity or self.DefaultCapacity

        self.LastDrip = time.time()
        self.Tokens = 0

    def drip(self):
        """Adds tokens to the bucket based on the configured drip rate
        per second, up to the capacity of the bucket.
        """
        now = time.time()
        self.Tokens = min(self.Capacity,
                          self.Tokens + int(self.DripRate *
                                            (now - self.LastDrip)))
        self.LastDrip = now

    def consume(self, amount):
        """Consumes tokens from the bucket.

        Args:
            amount (int): the number of tokens to consume from the bucket.

        Returns:
            bool: If more tokens are requested than are available, returns
                False, otherwise subtracts the tokens and returns True.

        """
        self.drip()

        if amount > self.Tokens:
            return False
        self.Tokens -= amount
        return True
