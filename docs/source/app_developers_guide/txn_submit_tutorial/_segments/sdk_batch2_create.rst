2. Create the Batch
-------------------

Using the SDK, creating a Batch is as simple as calling the *create* method and passing it one or more Transactions. If serialized, there is no need to decode them first, as the BatchEncoder can handle TransactionLists encoded as both raw binaries and url-safe base64 strings.
