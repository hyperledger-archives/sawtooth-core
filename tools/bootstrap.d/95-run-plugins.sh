#!/bin/bash

[[ -e /project ]] || exit 1

. /vagrant/conf.sh

cd /vagrant/plugins
for script in $PLUGINS
do
    echo "Running: ./$script.sh"
    ./$script.sh || exit 1
done

