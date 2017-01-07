#!/bin/bash -x

set -e

function install_requires {
    cat $1 \
        | grep -v "sawtooth-signing" \
        | grep -v "sawtooth-core" \
        | pip install -r /dev/stdin
}

# Packages for testing
pip install -r /project/sawtooth-core/tools/requirements-testing.txt

# sawtooth-core/signing
(cd /project/sawtooth-core/signing/ && python setup.py egg_info)
pip install -r /project/sawtooth-core/signing/sawtooth_signing.egg-info/requires.txt

# sawtooth-core/core
(cd /project/sawtooth-core/core/ && python setup.py egg_info)
pip install -r /project/sawtooth-core/core/sawtooth_core.egg-info/requires.txt

# sawtooth-core/validator
(cd /project/sawtooth-core/validator/ && python setup.py egg_info)
install_requires /project/sawtooth-core/validator/sawtooth_validator.egg-info/requires.txt

# sawtooth-core/extensions/mktplace
(cd /project/sawtooth-core/extensions/mktplace/ && python setup.py egg_info)
install_requires /project/sawtooth-core/extensions/mktplace/sawtooth_mktplace.egg-info/requires.txt

# sawtooth-core/extensions/bond
(cd /project/sawtooth-core/extensions/bond/ && python setup.py egg_info)
install_requires /project/sawtooth-core/extensions/bond/sawtooth_bond.egg-info/requires.txt

# sawtooth-core/extensions/arcade
(cd /project/sawtooth-core/extensions/arcade/ && python setup.py egg_info)
install_requires /project/sawtooth-core/extensions/arcade/sawtooth_arcade.egg-info/requires.txt
