3. Sign the Header
------------------

Once the TransactionHeader is created and serialized as a Protobuf binary, you can use your private key to create a secp256k1 signature. If not handled automatically by your signing library, you may need to generate a SHA-256 hash of the header bytes to be signed. The signature itself should be formatted as a hexedecimal string for transmission.