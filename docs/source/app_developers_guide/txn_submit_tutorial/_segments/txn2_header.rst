2. Build the TransactionHeader
------------------------------

Transactions and their headers are built using `Google Protocol Buffer <https://developers.google.com/protocol-buffers/>`_ (or Protobuf) format. This allows data to be serialized and deserialzed consistently and efficiently across multiple platforms and multiple languages. The Protobuf definition files are located in the `/protos directory <https://github.com/hyperledger/sawtooth-core/tree/master/protos>`_, at the root level of the sawtooth-core repo. These files will have to first be compiled into usable language-specific Protobuf classes. Then, serializing a *TransactionHeader* is just a matter of plugging the right data into the right keys.
