#!/bin/bash

PYTHONPATH=/project/sawtooth-core/core
PYTHONPATH=$PYTHONPATH:/project/sawtooth-core/signing
PYTHONPATH=$PYTHONPATH:/project/sawtooth-core/validator
PYTHONPATH=$PYTHONPATH:/project/sawtooth-core/extensions/arcade
PYTHONPATH=$PYTHONPATH:/project/sawtooth-core/sdk/python
PYTHONPATH=$PYTHONPATH:/project/sawtooth-core/sdk/examples
PYTHONPATH=$PYTHONPATH:/project/sawtooth-core/rest_api
PYTHONPATH=$PYTHONPATH:/project/sawtooth-core/consensus/poet/cli
PYTHONPATH=$PYTHONPATH:/project/sawtooth-core/consensus/poet/common
PYTHONPATH=$PYTHONPATH:/project/sawtooth-core/consensus/poet/common/tests
PYTHONPATH=$PYTHONPATH:/project/sawtooth-core/consensus/poet/core
PYTHONPATH=$PYTHONPATH:/project/sawtooth-core/consensus/poet/core/tests
PYTHONPATH=$PYTHONPATH:/project/sawtooth-core/consensus/poet/families
PYTHONPATH=$PYTHONPATH:/project/sawtooth-core/consensus/poet/families/tests
PYTHONPATH=$PYTHONPATH:/project/sawtooth-core/consensus/poet/simulator
PYTHONPATH=$PYTHONPATH:/project/sawtooth-core/consensus/poet/simulator/tests
export PYTHONPATH

GOPATH=/project/sawtooth-core/sdk/go
GOPATH=$GOPATH:/project/sawtooth-core/sdk/examples/intkey_go
GOPATH=$GOPATH:/project/sawtooth-core/sdk/examples/xo_go
GOBIN=/project/sawtooth-core/sdk/go/bin
export GOPATH

PATH=$PATH:$GOBIN:/project/sawtooth-core/bin:/
export PATH

export SAWTOOTH_HOME=/home/ubuntu/sawtooth
