#!/usr/bin/env bash

VER=$(lsb_release -sr)

if [ "$VER" = "16.04" ] ; then
    sudo apt-get install -y -q \
        openjdk-8-jdk \
        maven
else
    sudo apt-get install -y -q \
        openjdk-7-jdk \
        maven
fi
