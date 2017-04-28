5. (optional) Encode the Transaction(s)
---------------------------------------

If the same machine is creating Transactions and Batches there is no need to encode the Transaction instances. However, in the use case where Transactions are being batched externally, they must be serialized before being transmitted to the batcher. Since this batcher is likely something you have control over, technically any encoding scheme could be used, but Sawtooth does provide a *TransactionList* Protobuf for this purpose. Simply wrap a set of Transactions in the *transactions* property of a TransactionList and serialize it.
