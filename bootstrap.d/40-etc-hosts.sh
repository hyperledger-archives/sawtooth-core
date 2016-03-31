#!/bin/bash -x

cp /vagrant/guest-files/hosts /etc/hosts
chown root:root /etc/hosts
chmod 644 /etc/hosts
