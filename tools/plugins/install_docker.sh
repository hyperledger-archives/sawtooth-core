#!/bin/bash -x

. /vagrant/func.sh
. /vagrant/conf.sh

set -e

if [ ! -f /etc/debian_version ]; then
    echo "Skipping $0"
    exit 0
fi

VER=$(lsb_release -sr)

apt-key adv --keyserver hkp://p80.pool.sks-keyservers.net:80 --recv-keys 58118E89F3A912897C070ADBF76221572C52609D

if [ "$VER" = "16.04" ] ; then
    echo "deb https://apt.dockerproject.org/repo ubuntu-xenial main" > /etc/apt/sources.list.d/docker.list
else
    echo "deb https://apt.dockerproject.org/repo ubuntu-trusty main" > /etc/apt/sources.list.d/docker.list
fi
apt-get update

package_group_install docker

usermod -aG docker $VAGRANT_USER

echo "Logout and log back in to use docker"
