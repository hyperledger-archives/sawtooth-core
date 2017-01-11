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


VER=$(lsb_release -sr)
if [ "$VER" = "14.04" ] ; then
    if [ ! -f $pkg_dir/python-cbor_0.1.24-1_amd64.deb ]; then
        cd $build_dir
        wget https://pypi.python.org/packages/source/c/cbor/cbor-0.1.24.tar.gz
        tar xvfz cbor-0.1.24.tar.gz
        cd cbor-0.1.24
        python setup.py --command-packages=stdeb.command bdist_deb
        cp deb_dist/python-cbor*.deb $pkg_dir
    fi

    if [ ! -f $pkg_dir/python-colorlog_2.6.0-1_all.deb ]; then
        cd $build_dir
        wget https://pypi.python.org/packages/source/c/colorlog/colorlog-2.6.0.tar.gz
        tar xvfz colorlog-2.6.0.tar.gz
        cd colorlog-2.6.0
        python setup.py --command-packages=stdeb.command bdist_deb
        cp deb_dist/python-colorlog*.deb $pkg_dir
    fi
fi

if [ ! -f $pkg_dir/python-pybitcointools_1.1.15-1_all.deb ]; then
    cd $build_dir
    wget https://pypi.python.org/packages/source/p/pybitcointools/pybitcointools-1.1.15.tar.gz
    tar xvfz pybitcointools-1.1.15.tar.gz
    cd pybitcointools-1.1.15
    python setup.py --command-packages=stdeb.command bdist_deb
    cp deb_dist/python-pybitcointools*.deb $pkg_dir
fi
