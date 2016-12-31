#!/bin/sh

# This script sets the PYTHONPATH variable to the correct value for the current step of the
# transaction family tutorial.

PYTHONPATH=/project/sawtooth-core/core
PYTHONPATH=$PYTHONPATH:/project/sawtooth-core/docs/source/txn_family_tutorial/xo-tutorial-step04
PYTHONPATH=$PYTHONPATH:/project/sawtooth-core/signing
PYTHONPATH=$PYTHONPATH:/project/sawtooth-core/signing/build/lib.linux-x86_64-2.7
PYTHONPATH=$PYTHONPATH:/project/sawtooth-core/validator
PYTHONPATH=$PYTHONPATH:/project/sawtooth-core/sdk/python
PYTHONPATH=$PYTHONPATH:/project/sawtooth-core/
export PYTHONPATH
echo "Changed PYTHONPATH for step 04."
