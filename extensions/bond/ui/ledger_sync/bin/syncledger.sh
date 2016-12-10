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

if [ -z "$EXPLORERHOME" ] ; then
    echo EXPLORERHOME environment variable not set
    exit
fi

if [ -z "$EXPLORERETC" ] ; then
    export EXPLORERETC=$EXPLORERHOME/ledger-sync/etc
fi

if [ -z "$EXPLORERLOGS" ] ; then
    export EXPLORERLOGS=$EXPLORERHOME/ledger-sync/logs
fi


# -----------------------------------------------------------------
# -----------------------------------------------------------------
F_CLEAN='no'
F_CFILE='syncledger.js'
F_LOGLEVEL=''
F_REFRESH=''
F_URL=''
F_DBHOST=''
F_DBPORT=''

# -----------------------------------------------------------------
# Process command line arguments
# -----------------------------------------------------------------
TEMP=`getopt -o d:l:p:r:u: --long clean,config:,dbhost:,dbport:,loglevel:,refresh:,url: \
     -n 'ifxplayers.sh' -- "$@"`

if [ $? != 0 ] ; then echo "Terminating..." >&2 ; exit 1 ; fi

eval set -- "$TEMP"
while true ; do
    case "$1" in
        --clean)       F_CLEAN='yes' ; shift 1 ;;
        --config)      F_CFILE="$2" ; shift 2 ;;
        -d|--dbhost)   F_DBHOST="--dbhost $2" ; shift 2 ;;
        -p|--dbport)   F_DBPORT="--dbport $2" ; shift 2 ;;
        -r|--refresh)  F_REFRESH="--refresh $2"    ; shift 2 ;;
        -l|--loglevel) F_LOGLEVEL="--loglevel $2" ; shift 2 ;;
        -u|--url)      F_URL="--url $2"      ; shift 2 ;;
 	--) shift ; break ;;
	*) echo "Internal error!" ; exit 1 ;;
    esac
done


# -----------------------------------------------------------------
cd $EXPLORERHOME/ledger-sync

if [[ ":$PYTHONPATH:" != *":$EXPLORERHOME/ledger-sync:"* ]]; then
    export PYTHONPATH=$PYTHONPATH:$EXPLORERHOME/ledger-sync
fi

if [[ ! -e $EXPLORERHOME/ledger-sync/logs ]]; then
    mkdir $EXPLORERHOME/ledger-sync/logs
fi

if [ $F_CLEAN == 'yes' ] ; then 
    ## echo ========== Clean Log Directories ==========
    rm -f $EXPLORERHOME/ledger-sync/logs/*
fi

echo $EXPLORERHOME/ledger-sync/scripts/syncledger --config $F_CFILE $F_REFRESH $F_LOGLEVEL $F_URL $F_DBHOST $F_DBPORT
screen -L -S syncledger -p - -d -m \
    $EXPLORERHOME/ledger-sync/scripts/syncledger --config $F_CFILE $F_REFRESH $F_LOGLEVEL $F_URL $F_DBHOST $F_DBPORT --logfile __screen__
