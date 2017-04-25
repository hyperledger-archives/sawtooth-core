2. Create the BatchHeader
-------------------------

The process for creating a *BatchHeader* is very similar to a *TransactionHeader*. Compile the *batches.proto* file, and then instantiate the appropriate class with the appropriate values. In this case, there are just two properties: a *signer pubkey*, and a set of *Transaction ids*. Just like with a TransactionHeader, the signer pubkey must have been generated from the private key used to sign the Batch. The Transaction ids are a list of the *header signatures* from the Transactions to be batched. They must be in the same order as the Transactions themselves.
