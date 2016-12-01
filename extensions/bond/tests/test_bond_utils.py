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

import unittest

import random

from sawtooth_bond.bond_utils import float_to_bondprice, bondprice_to_float


class TestBondUtils(unittest.TestCase):

    def setUp(self):
        self.floatkeys_bondpricevalues = {98.46875: '98-15',
                                          92.84375: '92-27',
                                          92.515625: '92-16+', 89: '89-0',
                                          89.015625: '89-0+',
                                          58.5078125: '58-16 1/4',
                                          89.00390625: '89-0 1/8',
                                          98.9375: '98-30',
                                          67.44921875: '67-14 3/8'}
        self.bondpricekeys_floatvalues = {'75': 75.0, '85-31+': 85.984375,
                                          '86-12': 86.375, '75-0': 75.0,
                                          '85-0 1/4': 85.0078125,
                                          '58-16 1/4': 58.5078125,
                                          '67-14 3/8': 67.44921875,
                                          }

    def test_float_to_bondprice(self):
        for f, bp in self.floatkeys_bondpricevalues.iteritems():
            self.assertEqual(float_to_bondprice(f), bp,
                             "Converted from {} to {}, not {}".
                             format(f, float_to_bondprice(f), bp))

    def test_bondprice_to_float(self):
        for bp, f in self.bondpricekeys_floatvalues.iteritems():
            self.assertEqual(bondprice_to_float(bp), f,
                             "Converted from {} to {}, not {}".
                             format(bp, bondprice_to_float(bp), f))

    def test_assuming_ftb_is_correct(self):
        random_floats = [random.random() * 100 for _ in xrange(100)]
        for f in random_floats:
            bp = float_to_bondprice(f)
            self.assertEqual(bondprice_to_float(bp), f,
                             "Converted from {} to {}, not {}".
                             format(bp, bondprice_to_float(bp), f))

    def test_assuming_btf_is_correct(self):
        random_bp = ["{}-{}".format(random.randint(0, 100),
                                    random.randint(0, 31))
                     for _ in xrange(100)]
        for bp in random_bp:
            f = bondprice_to_float(bp)
            self.assertEqual(float_to_bondprice(f), bp,
                             "Converted from {} to {}, not {}".
                             format(f, float_to_bondprice(f), bp))
