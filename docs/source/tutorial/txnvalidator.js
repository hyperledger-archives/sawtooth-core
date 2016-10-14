{
    "Listen" : [
        "localhost:5500/UDP gossip",
        "localhost:8800/TCP http"
    ],
    ## configuration of publicly-visible endpoint information
    ## used if validator is behind NAT
    ##"Endpoint" : {
    ##      "Host" : "localhost",
    ##      "Port" : 5500,
    ##      "HttpPort" : 8800
    ##},
    "NodeName" : "base000",
    "LedgerURL" : ["http://localhost:8800/"],

    ## pick the ledger type
    "LedgerType" : "poet0",
    "GenesisLedger" : true,

    ## configuration of the ledger wait time certificate 
    ## suggested settings for single node dev environment
    "TargetWaitTime" : 5.0,
    "InitialWaitTime" : 5.0,
    "CertificateSampleLength" : 30,

    ## suggested settings for a 25 node network
    ## "TargetWaitTime" : 30.0,
    ## "InitialWaitTime" : 750.0,

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

    ## configuration of the transaction families to include
    ## in the validator
    "TransactionFamilies" : [
        "ledger.transaction.integer_key"
    ],

    ## This value should be set to the identifier which is
    ## permitted to send shutdown messages on the network.
    ## By default, no AdministrationNode is set.
    ## "AdministrationNode" : "19ns29kWDTX8vNeHNzJbJy6S9HZiqHZyEE",

    ## key file
    "KeyFile" : "{key_dir}/{node}.wif"
}
