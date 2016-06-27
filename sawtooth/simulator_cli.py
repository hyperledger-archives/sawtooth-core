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
import sys
import argparse

from sawtooth.simulator import SawtoothWorkloadSimulator


def parse_args(args):
    parser = argparse.ArgumentParser()

    parser.add_argument('--url',
                        metavar="",
                        help='Base validator URL (default: %(default)s)',
                        default="http://localhost:8800")
    parser.add_argument('--workload',
                        help='Transaction workload (default: %(default)s)',
                        default='sawtooth_xo.xo_workload.XoWorkload')
    parser.add_argument('--rate',
                        help='Transaction rate in transactions per minute'
                             '(default: %(default)s)',
                        type=int,
                        default=12)

    return parser.parse_args(args)


def main(name=os.path.basename(sys.argv[0]), args=sys.argv[1:]):

    opts = parse_args(args)
    simulator = SawtoothWorkloadSimulator(opts)

    try:
        simulator.run()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
