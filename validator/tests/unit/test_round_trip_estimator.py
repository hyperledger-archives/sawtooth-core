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

from gossip.node import RoundTripEstimator


class TestRoundTripEstimator(unittest.TestCase):

    def test_round_trip_estimator_init(self):
        # Test default init of RoundTripEstimator
        rte = RoundTripEstimator()
        self.assertEqual(rte.RTO, 1.0)
        self.assertEqual(rte._SRTT, 0.0)
        self.assertEqual(rte._RTTVAR, 0.0)

    def test_round_trip_estimator_update_once(self):
        # Test that .update() updates RTO, SRTT, and RTTVAR as expected
        rte = RoundTripEstimator()
        rte.update(5.0)
        # New RTO is calcualted useing the newley updated _SRTT and _RTTVAR
        self.assertEqual(rte.RTO, 15)
        self.assertEqual(rte._SRTT, 5.0)
        self.assertEqual(rte._RTTVAR, 2.5)
        rte.update(5.0)
        self.assertNotEqual(rte.RTO, 15)
        self.assertEqual(rte._SRTT, 5.0)
        self.assertNotEqual(rte._RTTVAR, 2.5)

    def test_round_trip_estimator_update_multiple(self):
        # Test that RTP converges on correct number if it is consistent
        rte = RoundTripEstimator()
        self.assertEqual(rte.RTO, 1.0)
        self.assertEqual(rte._SRTT, 0.0)
        self.assertEqual(rte._RTTVAR, 0.0)
        for i in range(100):
            rte.update(5.0)
        # Converges on 5 + MinResolution
        self.assertEqual(rte.RTO, 5.025)

        for i in range(100):
            rte.update(64.0)
        # Should not excede MaximumRTO ~ 60
        self.assertEqual(rte.RTO, rte.MaximumRTO)

    def test_round_trip_estimator_backoff_once(self):
        # Test one backoff.
        rte = RoundTripEstimator()
        rte.backoff()
        # Should reset SRTT and RTTVAR while multipling RTP by BackoffRate ~ 2
        self.assertEqual(rte._SRTT, 0.0)
        self.assertEqual(rte._RTTVAR, 0.0)
        self.assertEqual(rte.RTO, 2)

    def test_round_trip_estimator_backoff_multiple(self):
        # Test that RTO will not exceed MaximumRTO after repeated backoffs
        rte = RoundTripEstimator()
        for i in range(10):
            rte.backoff()
        self.assertEqual(rte._SRTT, 0.0)
        self.assertEqual(rte._RTTVAR, 0.0)
        self.assertEqual(rte.RTO, rte.MaximumRTO)
