#!/bin/bash

. /vagrant/conf.sh

set -e

/project/sawtooth-core/bin/install_packaging_deps

pkg_dir=/home/$VAGRANT_USER/packages
build_dir=/home/$VAGRANT_USER/projects

mkdir -p $pkg_dir && mkdir -p $build_dir
/project/sawtooth-core/bin/build_ext_debs -p $pkg_dir -b $build_dir
