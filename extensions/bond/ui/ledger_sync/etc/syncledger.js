{
    ## configuration of logging
    "LogLevel" : "INFO",
    "LogFile"  : "${logs}/ledgersync.log",

    ## location of the ledger
    "LedgerURL" : "http://localhost:8800",

    ## synchronization configuration
    "Refresh" : 20,
    "BlockCount" : 10,
    "FullSyncInterval" : 50,

    ## database and collection names
    "DatabaseHost" : "localhost",
    "DatabasePort" : 28015,
    "DatabaseName" : "bond",

    "BlockCollection" : "blocks",
    "CertCollection" : "waitcerts",
    "TxnCollection" : "transactions"
}
