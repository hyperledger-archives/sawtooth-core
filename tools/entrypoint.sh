#!/bin/bash
set -e

if [ "$#" == 0 ]; then
    exec ./bin/txnvalidator -v --http 8800 --config /project/sawtooth-docs/source/tutorial/txnvalidator.js "$@"
fi

exec "$@"
