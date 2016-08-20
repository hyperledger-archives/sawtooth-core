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

import argparse
import os
import sys

import pybitcointools


def main(args=sys.argv[1:]):
    parser = argparse.ArgumentParser()

    # The intent is that node_name and keydir both be optional at some
    # future point, by reading in the appropriate values from the config
    # file.  Therefore, no default is currently set and both are marked
    # as required so that the future usage of using config values as
    # defaults can be added without breaking anything.
    parser.add_argument('node_name', help="name of the node")
    parser.add_argument('--keydir',
                        help="directory to write key files",
                        required=True)
    parser.add_argument('-f',
                        '--force',
                        help="overwrite files if they exist",
                        action='store_true')
    parser.add_argument('-q',
                        '--quiet',
                        help="print no output",
                        action='store_true')

    options = parser.parse_args(args)

    base_filename = os.path.join(options.keydir, options.node_name)
    wif_filename = base_filename + ".wif"
    addr_filename = base_filename + ".addr"

    if not os.path.isdir(options.keydir):
        print >> sys.stderr, "no such directory: {}".format(options.keydir)
        sys.exit(1)

    if not options.force:
        file_exists = False
        for filename in [wif_filename, addr_filename]:
            if os.path.exists(filename):
                file_exists = True
                print >> sys.stderr, "file exists: {}".format(filename)
        if file_exists:
            print >> sys.stderr, \
                "rerun with --force to overwrite existing files"
            sys.exit(1)

    privkey = pybitcointools.random_key()

    encoded = pybitcointools.encode_privkey(privkey, 'wif')
    addr = pybitcointools.privtoaddr(privkey)

    try:
        wif_exists = os.path.exists(wif_filename)
        with open(wif_filename, "w") as wif_fd:
            if not options.quiet:
                if wif_exists:
                    print "overwriting file: {}".format(wif_filename)
                else:
                    print "writing file: {}".format(wif_filename)
            wif_fd.write(encoded)
            wif_fd.write("\n")

        addr_exists = os.path.exists(addr_filename)
        with open(addr_filename, "w") as addr_fd:
            if not options.quiet:
                if addr_exists:
                    print "overwriting file: {}".format(addr_filename)
                else:
                    print "writing file: {}".format(addr_filename)
            addr_fd.write(addr)
            addr_fd.write("\n")
    except IOError, ioe:
        print >> sys.stderr, "IOError: {}".format(str(ioe))
        sys.exit(1)
