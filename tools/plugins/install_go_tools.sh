#!/bin/bash -x

. /vagrant/conf.sh

set -e

apt-get install -y -q \
    golang


export GOPATH=/home/$VAGRANT_USER/go

go get -u \
    github.com/golang/protobuf/proto \
    github.com/golang/protobuf/protoc-gen-go \
    github.com/pebbe/zmq4

chown -R $VAGRANT_USER:$VAGRANT_USER $GOPATH
chown -R $VAGRANT_USER:$VAGRANT_USER $GOPATH/bin
