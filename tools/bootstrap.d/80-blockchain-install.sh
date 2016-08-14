#!/bin/bash -x

[[ -e /project ]] || exit 1

. /vagrant/conf.sh

if [[ "$INSTALL_TYPE" != "setup.py" ]]; then
    echo "Skipping: $0"
    exit 0
fi

set -e

cd /project/sawtooth-core/core
python setup.py build
python setup.py install 

cd /project/sawtooth-core/extensions/mktplace
python setup.py build
python setup.py install 

cd /project/sawtooth-core/validator
python setup.py build
python setup.py install 
