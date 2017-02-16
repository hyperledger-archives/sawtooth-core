{
    "Listen" : [
        "0.0.0.0:5500/UDP gossip",
        "0.0.0.0:8800/TCP http"
    ],

    "Endpoint" : {
        "Host" : "localhost",
        "Port" : 5500,
        "HttpPort" : 8800
     },

    "NodeName" : "ubuntu",

    "LedgerURL" : [
    ],

    "Peers" : [
    ],

    ## pick the ledger type
    "LedgerType" : "poet1",
    "InitialConnectivity" : 0,

    ## backing store
    "StoreType" : "lmdb",

    ## Worker Limits
    "WebPoolSize" : 32,
    "MaxWebWorkers" : 31,

    ## configuration of the ledger wait time certificate
    "TargetWaitTime" : 20.0,
    "InitialWaitTime" : 150.0,
    "CertificateSampleLength" : 30,

    ## configuration of the block sizes
    "MinTransactionsPerBlock" : 1,
    "MaxTransactionsPerBlock" : 1000,

    ## configuration of the topology
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
        "ledger.transaction.integer_key",
        "sawtooth_bond"
    ],

    ## administration node, the only node identifier from which
    ## we will accept shutdown messages
    "AdministrationNode" : "NOT_SET",

    ## key file
    "KeyFile" : "/home/ubuntu/.sawtooth/keys/ubuntu.wif"
}
