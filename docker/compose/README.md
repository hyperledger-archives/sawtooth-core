# Overview

Docker is used extensively by core developers for building and testing the
individual components of Sawtooth. This directory provides a set of Docker
Compose files for starting up an environment useful for developing new
transaction families and clients.

# Prerequisites

This tutorial assumes you have already cloned the repo:

    $ git clone https://github.com/hyperledger/sawtooth-core

This tutorial also assumes you have Docker Compose installed.

# Setting up the Environment

First, decide which language you want to use. Currently the following languages
are supported for use with Docker Compose:
    * Go (1.6)
    * Python (3.5)
    * Java
    * Javascript

The Docker Compose environment reads an environment variable to determine where
your project directory lives. Set the PROJECT environment variable before
starting up the environment to mount your project directory into the
development container:

    $ export PROJECT=/my/project/direcotry

We can now startup the environment. Replace LANGUAGE with one of {go, python,
java, javascript} and then run the command:

    $ docker-compose \
        -f sawtooth-core/docker/compose/sawtooth-dev-base.yaml \
        -f sawtooth-core/docker/compose/sawtooth-dev-LANGUAGE.yaml \
        up

This will startup and configure Docker containers for the:
    * Validator
    * REST API
    * Config Transaction Processor
    * Sawtooth CLI

These four components provide all the functionality you should need to connect
a new transction processor to a running validator for testing.

A final container is started which is configured to talk to the REST API and
validator and has the Sawtooth SDK for the language you selected installed and
ready for importing. It will have the directory you set in PROJECT mounted to
`/project`. To connect to the container, do:

    $ docker exec -it compose_dev_1 bash

This will drop you into a new shell inside the container in the /project
directory. If everything worked, you should see your code in the directory. 

You can now build your code based on the Sawtooth SDK and communicate with the
validator and REST API.

# Connecting to the Validator and REST API

Docker Compose provides a DNS

To connect a transaction processor to the running validator in the development
environment, use this URI:

    tcp://validator:40000

To connect a client to the running REST API container in the development
environment, use this URI:

    http://rest_api:8080

# Stopping the Environment

To stop the environment when it is running, do:

    $ docker-compose \
        -f sawtooth-core/docker/compose/sawtooth-dev-base.yaml \
        -f sawtooth-core/docker/compose/sawtooth-dev-LANGUAGE.yaml \
        down 

This will destroy the containers that were created before. Since your project
directory was mounted into the docker container, it will be untouched by this.
