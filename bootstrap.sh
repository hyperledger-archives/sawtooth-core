#!/bin/bash -x

cd /vagrant || exit 1

for script in $(ls -1 bootstrap.d/*.sh | sort -n)
do
    echo "Running: ./$script"
    ./$script || exit 1
done

