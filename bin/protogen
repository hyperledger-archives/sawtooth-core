#!/usr/bin/env python3
#
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

import os
import tempfile
from glob import glob
import re


try:
    from grpc.tools.protoc import main as _protoc
except ImportError:
    print("Error: protoc not found.")
    exit(1)


JOIN = os.path.join
TOP_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))


def main():
    # 1. Generate and distribute top-level protos
    proto_dir = JOIN(TOP_DIR, "protos")
    run_protoc(proto_dir, "sdk/python", "sawtooth_protobuf")
    run_protoc(proto_dir, "validator", "sawtooth_validator/protobuf")

    # 2. Generate config protos
    config_dir = "core_transactions/config"
    proto_dir = JOIN(TOP_DIR, config_dir, "protos")
    run_protoc(proto_dir, config_dir, "sawtooth_config/protobuf")


def run_protoc(src_dir, base_dir, pkg):
    # 1. Create output package directory
    pkg_dir = JOIN(TOP_DIR, base_dir, pkg)
    os.makedirs(pkg_dir, exist_ok=True)

    # 2. 'touch' the __init__.py file if the output directory exists
    init_py = JOIN(pkg_dir, "__init__.py")
    if os.path.exists(init_py):
        os.utime(init_py)

    # 3. Create a temp directory for building
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_pkg_dir = JOIN(tmp_dir, pkg)
        os.makedirs(tmp_pkg_dir)

        # 4. Get a list of all .proto files to build
        cwd = os.getcwd()
        os.chdir(src_dir)
        proto_files = glob("*.proto")
        os.chdir(cwd)

        # 5. Copy protos to temp dir and fix imports
        for proto in proto_files:
            src = JOIN(src_dir, proto)
            dst = JOIN(tmp_pkg_dir, proto)
            with open(src) as fin:
                with open(dst, "w") as fout:
                    fout.write(fix_import(fin.read(), pkg))

        # 6. Compile protobuf files
        protoc([
            "-I=%s" % tmp_dir,
            "--python_out=%s" % base_dir,
        ] + glob("%s/*.proto" % tmp_pkg_dir))


def fix_import(contents, pkg):
    pattern = r'^import "(.*)\.proto\"'
    template = r'import "%s/\1.proto"'

    # Lambda expression is used to interpolate the pkg name
    return re.sub(
        pattern,
        lambda match: match.expand(template) % pkg,
        contents,
        flags=re.MULTILINE
    )

def protoc(args):
    # Need the calling file to be the first arg when calling
    # grcp.tools.protoc.main() directly
   _protoc([__file__] + args)


if __name__ == "__main__":
    main()
