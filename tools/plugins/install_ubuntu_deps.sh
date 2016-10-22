#!/bin/bash

set -e

root=/project
build_dir=$root/build
pkg_dir=$build_dir/packages


VER=$(lsb_release -sr)
if [ "$VER" = "16.04" ] ; then
    cd $pkg_dir
    dpkg -i \
        python-pybitcointools_1.1.15-1_all.deb
else
    cd $pkg_dir
    dpkg -i \
        python-cbor_0.1.24-1_amd64.deb \
        python-colorlog_2.6.0-1_all.deb \
        python-pybitcointools_1.1.15-1_all.deb
fi
