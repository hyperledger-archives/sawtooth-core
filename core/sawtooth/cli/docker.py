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

from __future__ import print_function

import logging
import os
import tempfile
import shutil
import subprocess

from sawtooth.cli.exceptions import CliException


LOGGER = logging.getLogger(__name__)


def add_docker_parser(subparsers, parent_parser):
    parser = subparsers.add_parser('docker', parents=[parent_parser])

    docker_subparsers = parser.add_subparsers(
        title='subcommands',
        dest='docker_command')

    add_docker_build_parser(docker_subparsers, parent_parser)


def add_docker_build_parser(subparsers, parent_parser):
    build_parser = subparsers.add_parser('build', parents=[parent_parser])
    build_parser.add_argument('--all',
                              help='build all the images',
                              default=False,
                              action='store_true')
    build_parser.add_argument('filename',
                              help='specify Dockerfile filenames to build',
                              nargs='*')


def do_docker(args):
    if args.docker_command == 'build':
        do_docker_build(args)
    else:
        raise CliException("invalid docker command: {}".format(
            args.docker_command))


def _build_docker_image(image):
    image_src = os.path.join(
        os.path.dirname(__file__),
        "data",
        image)

    tmpdir = tempfile.mkdtemp(prefix='sawtooth-docker-')
    try:
        try:
            shutil.copyfile(image_src, os.path.join(tmpdir, "Dockerfile"))
        except IOError as e:
            raise CliException("Failed to copy Dockerfile: {}".format(str(e)))

        args = ['docker', 'build', '-t', image, tmpdir]
        try:
            subprocess.check_call(args)
        except OSError as e:
            raise CliException("Failed to run '{}': {}".format(
                " ".join(args), str(e)))
    finally:
        shutil.rmtree(tmpdir)


def do_docker_build(args):
    if args.all:
        for image in ['sawtooth-build-ubuntu-xenial',
                      'sawtooth-dev-ubuntu-xenial']:
            print("Building docker image: {}".format(image))
            _build_docker_image(image)
    elif args.filename is not None:
        for image in args.filename:
            _build_docker_image(image)
            print("Building docker image: {}".format(image))
    else:
        print("Specify a dockerfile or use --all")
