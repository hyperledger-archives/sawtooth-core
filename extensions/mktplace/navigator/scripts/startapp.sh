#!/bin/bash

# Copyright 2016 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ------------------------------------------------------------------------------

# Would be nice to be able to set listening port

if [ -z "$EXPLORERHOME" ] ; then
    echo EXPLORERHOME environment variable not set
    exit
fi

if [ -z "$LEDGER_URL" ] ; then
    export LEDGER_URL=http://127.0.0.1:8900
fi

# -----------------------------------------------------------------
# -----------------------------------------------------------------
F_DBNAME=ledger
F_DBPORT=28015
F_DBHOST=localhost

F_MODE=production

F_SERVERPORT=3000
F_URL=$LEDGER_URL

# -----------------------------------------------------------------
# Process command line arguments
# -----------------------------------------------------------------
TEMP=`getopt -o p:u: --long port:,url: \
     -n 'startapp.sh' -- "$@"`

if [ $? != 0 ] ; then echo "Terminating..." >&2 ; exit 1 ; fi

eval set -- "$TEMP"
while true ; do
    case "$1" in
        -p|--port) F_PORT="$2"; shift 2 ;;
        -u|--url)  F_URL="$2"      ; shift 2 ;;
 	--) shift ; break ;;
	*) echo "Internal error!" ; exit 1 ;;
    esac
done

# set up the environment variables
export PORT=$F_PORT
export LEDGER_URL=$F_URL
export NODE_ENV=$F_MODE

# start the server
cd $EXPLORERHOME/server

screen -L -S explorer -p - -d -m npm start
screen -L -S wallet -p - -d -m npm run start:wallet-sim

# start the client
if [ $F_MODE != 'production' ]; then
    cd $EXPLORERHOME/client

    screen -L -S client -p - -d -m scripts/figwheel.sh
fi

# start the ledger sync
cd $EXPLORERHOME/ledger-sync

bin/syncledger.sh --url $LEDGER_URL --clean
