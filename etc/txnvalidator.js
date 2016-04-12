{
    "HttpPort" : 0,
    "Host" : "localhost",
    "Port" : 0,
    "NodeName" : "base000",
    "LedgerURL" : "http://localhost:8800/",

    ## pick the ledger type
    "LedgerType" : "lottery",
    "GenesisLedger" : true,

    ## configuration of the ledger wait time certificate 
    "TargetWaitTime" : 30.0,
    "InitialWaitTime" : 750.0,
    "CertificateSampleLength" : 30,

    ## configuration of the block sizes
    "MinTransactionsPerBlock" : 1,
    "MaxTransactionsPerBlock" : 1000,

    ## configuration of the topology
    ## "TopologyAlgorithm" : "BarabasiAlbert",
    ## "MaximumConnectivity" : 15,
    ## "MinimumConnectivity" : 1,

    "TopologyAlgorithm" : "RandomWalk",
    "TargetConnectivity" : 3,

    ## configuration of the network flow control
    "NetworkFlowRate" : 96000,
    "NetworkBurstRate" : 128000,
    "NetworkDelayRange" : [ 0.00, 0.10 ],
    "UseFixedDelay" : true,

    ## configuration of logging
    "LogLevel" : "INFO",
    "LogFile"  : "{log_dir}/lottery-{node}.log",

    ## configuration of the transaction families to include
    ## in the validator
    "TransactionFamilies" : [
        "ledger.transaction.integer_key"
    ],

    ## do not restart 
    "Restore" : false,

    ## administration node, the only node identifier from which
    ## we will accept shutdown messages
    "AdministrationNode" : "19ns29kWDTX8vNeHNzJbJy6S9HZiqHZyEE",

    ## key file
    "KeyFile" : "{key_dir}/{node}.wif"
}
