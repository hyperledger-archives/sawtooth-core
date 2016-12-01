#!/bin/sh

# This script sets the PYTHONPATH variable to the correct value for the current step of the
# transaction family tutorial.

export PYTHONPATH=/project/sawtooth-core/core:/project/sawtooth-core/docs/source/txn_family_tutorial/xo-tutorial-step01:/project/sawtooth-core/signing:/project/sawtooth-core/signing/build/lib.linux-x86_64-2.7:/project/sawtooth-core/validator:/project/sawtooth-core/validator/build/lib.linux-x86_64-2.7:/project/sawtooth-core/sdk/python:/project/sawtooth-core/
echo "Changed PYTHONPATH for step 01."
