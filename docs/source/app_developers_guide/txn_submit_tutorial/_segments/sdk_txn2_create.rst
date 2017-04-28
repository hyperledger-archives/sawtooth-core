2. Create the Transaction
-------------------------

The only additional arguments required to create a Transaction is the payload itself, and if a *payload encoder* was set, you can even skip the step of manuaually binary-encoding the data. Optionally, you may override some of the default elements set in the TransactionEncoder on a Transaction by Transaction basis.