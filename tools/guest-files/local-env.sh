#!/bin/bash

PYTHONPATH=/project/sawtooth-core/core
PYTHONPATH=$PYTHONPATH:/project/sawtooth-core/signing
PYTHONPATH=$PYTHONPATH:/project/sawtooth-core/validator
PYTHONPATH=$PYTHONPATH:/project/sawtooth-core/extensions/arcade
PYTHONPATH=$PYTHONPATH:/project/sawtooth-core/sdk/python
PYTHONPATH=$PYTHONPATH:/project/sawtooth-core/sdk/examples
PYTHONPATH=$PYTHONPATH:/project/sawtooth-core/rest_api
export PYTHONPATH

PATH=$PATH:/project/sawtooth-core/bin
export PATH

export SAWTOOTH_HOME=/home/ubuntu/sawtooth
