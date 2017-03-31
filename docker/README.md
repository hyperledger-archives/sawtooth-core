Sawtooth Lake - Docker
----------------------

The Dockerfiles in this folder serve the following purposes:

    1. Encapsulate the build environment
    2. Provide a reproducible testing and development environment
    3. Generate fully containerized images for publishing

The purpose served by individual Dockerfiles can be identified by the naming
convention described below. See the individual Dockerfiles for additional
details and usage.

A docker compose file is also provided in the compose/ directory to demonstrate
starting up a single validator network with several transaction processors
connected.

## sawtooth-build-\*

Dockerfiles used to build the Sawtooth Lake source code without polluting the
host environment. The containers should be run with the source code mounted
inside the container.

These Dockerfiles are built and run as part of the `build_all` command.

## sawtooth-dev-\*

Dockerfiles used for testing and development. 

These Dockerfiles are built as part of the `build_all` command and run as part
of the `run_tests` command.

## sawtooth-\*

Dockerfiles that build images with Sawtooth Lake installed from the Sawtooth
Lake package repository. (repo.sawtooth.me) These Dockerfiles do not make any
assumptions about the build or runtime environments.
