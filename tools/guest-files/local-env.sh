#!/bin/bash

[ -d /home/ubuntu/sawtooth ] && export CURRENCYHOME=/home/ubuntu/sawtooth || export CURRENCYHOME=/project/sawtooth-core/validator

PYTHONPATH=/project/sawtooth-core/core
PYTHONPATH=$PYTHONPATH:/project/sawtooth-core/signing
PYTHONPATH=$PYTHONPATH:/project/sawtooth-core/signing/build/lib.linux-x86_64-2.7
PYTHONPATH=$PYTHONPATH:/project/sawtooth-core/validator
PYTHONPATH=$PYTHONPATH:/project/sawtooth-core/validator/build/lib.linux-x86_64-2.7
PYTHONPATH=$PYTHONPATH:/project/sawtooth-core/extensions/mktplace
PYTHONPATH=$PYTHONPATH:/project/sawtooth-core/extensions/bond
PYTHONPATH=$PYTHONPATH:/project/sawtooth-core/extensions/arcade
export PYTHONPATH

PATH=$PATH:/project/sawtooth-core/bin
export PATH
