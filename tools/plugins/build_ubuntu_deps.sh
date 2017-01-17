#!/bin/bash

set -e


if [ ! -f /etc/debian_version ]; then
    echo "Skipping $0"
    exit 0
fi

build_dir=/tmp/build
pkg_dir=/project/build/packages

mkdir -p $build_dir
mkdir -p $pkg_dir

if [ ! -f $pkg_dir/python-pybitcointools_1.1.15-1_all.deb ]; then
    cd $build_dir
    wget https://pypi.python.org/packages/source/p/pybitcointools/pybitcointools-1.1.15.tar.gz
    tar xvfz pybitcointools-1.1.15.tar.gz
    cd pybitcointools-1.1.15
    python setup.py --command-packages=stdeb.command bdist_deb
    cp deb_dist/python-pybitcointools*.deb $pkg_dir
fi
