#!/bin/bash

# A simple test to verify that the each systemd service is able to startup
# without immediately crashing given the default arguments

services="
validator
rest_api
tp_intkey_python
tp_config
tp_validator_registry
"

if [ -z $ISOLATION_ID ]
then
    ISOLATION_ID=latest
fi

for serv in $services
do
    # 1. Create a docker container running systemd
    image=sawtooth-$serv:$ISOLATION_ID 
    container=${ISOLATION_ID}_systemd_test_$serv
    service=sawtooth-$serv
    echo "Starting container '$container' from '$image'..."
    docker run -d --name $container --privileged --rm $image systemd
    sleep 1 # Give systemd a chance to start

    if [ $serv = "validator" ]
    then
        echo "Running keygen in $container..."
        docker exec $container sawtooth admin keygen
    fi

    # 2. Start the systemd service in the container
    echo "Starting $service in $container..."
    docker exec $container systemctl start $service
    sleep 1 # Give the service a chance to fail

    # 3. Check if the service started successfully
    docker exec $container systemctl status $service
    exitcode=$?
    echo "Exit code was $exitcode"

    # 4. Cleanup the container
    docker kill $container

    if [ $exitcode -ne 0 ]
    then
        exit $exitcode
    fi
done
