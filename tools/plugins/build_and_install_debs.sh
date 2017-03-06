#!/bin/bash

. /vagrant/conf.sh

set -e

apt-get install -y -q \
    autoconf \
    automake \
    build-essential \
    connect-proxy \
    g++ \
    git \
    libffi-dev \
    libgmp-dev \
    libtool \
    make \
    pkg-config \
    python-all-dev \
    python3-all-dev \
    rsync \
    sudo \
    wget \
    zip unzip

apt-get install -y -q \
    python-setuptools \
    python3-appdirs \
    python3-cbor \
    python3-cffi \
    python3-cffi \
    python3-colorlog \
    python3-pip \
    python3-pkgconfig \
    python3-pycparser \
    python3-pytest \
    python3-setuptools \
    python3-stdeb \
    python3-yaml \
    python3-zmq

pkg_dir=/home/$VAGRANT_USER/packages
build_dir=/home/$VAGRANT_USER/projects

mkdir -p $pkg_dir && mkdir -p $build_dir
/project/sawtooth-core/bin/build_ext_debs -p $pkg_dir -b $build_dir
