#!/bin/bash -x

[[ -e /project ]] || exit 1

. /vagrant/conf.sh

if [[ "$INSTALL_TYPE" != "deb" ]]; then
    echo "Skipping: $0"
    exit 0
fi

set -e

/vagrant/scripts/create_ubuntu_release_tar
/vagrant/scripts/install_ubuntu_release_tar

