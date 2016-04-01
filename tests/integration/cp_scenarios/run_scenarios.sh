#!/usr/bin/env bash
# this is a utility script that runs the exact load as the test_cp_scenarios
# it is useful for creating load and debugging the cp tests
#
# this script can be run from the command line in the vagrant environment

export CURRENCYHOME="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

LogLevel=DEBUG
LogFile=scenario.log
ARGS="--echo --loglevel=$LogLevel --logfile $LogFile"


mktclient --name mkt --script scenario_setup_1_mkt $ARGS
mktclient --name BANK-trader --script scenario_setup_2_trader $ARGS
mktclient --name BANK-agent --script scenario_setup_3_agent $ARGS
mktclient --name BANK-dealer --script scenario_setup_4_dealer $ARGS
read -n1 -r -p "Press any key to continue..." key

mktclient --name BANK-trader --script scenario_a_1_trader $ARGS
mktclient --name BANK-agent --script scenario_a_2_agent $ARGS
read -n1 -r -p "Press any key to continue..." key

mktclient --name BANK-trader --script scenario_b_1_trader $ARGS
mktclient --name BANK-dealer --script scenario_b_2_dealer $ARGS
read -n1 -r -p "Press any key to continue..." key

mktclient --name BANK-trader --script scenario_b_1_trader $ARGS
mktclient --name BANK-dealer --script scenario_b_2_dealer $ARGS
read -n1 -r -p "Press any key to continue..." key

mktclient --name BANK-trader --script scenario_c_1_trader $ARGS
mktclient --name BANK-dealer --script scenario_c_2_dealer $ARGS
mktclient --name BANK-agent --script scenario_c_3_agent $ARGS
mktclient --name BANK-agent --script scenario_c_4_dealer $ARGS
read -n1 -r -p "Press any key to continue..." key

mktclient --name BANK-trader --script scenario_d_1_trader $ARGS
mktclient --name BANK-agent --script scenario_d_2_agent $ARGS
read -n1 -r -p "Press any key to continue..." key