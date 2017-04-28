1. Create an Encoder
--------------------

A *TransactionEncoder* stores your private key, and (optionally) default TransactionHeader values and a function to encode each payload. Once instantiated, multiple Transactions can be created using these common elements, and without any explicit hashing or signing.
