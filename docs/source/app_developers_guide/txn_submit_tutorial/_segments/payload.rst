Encoding your Payload
=====================

Transaction payloads are composed of binary-encoded data that is opaque to the validator. The logic for encoding and decoding them rests entirely within the particular Transaction Processor itself. As a result, there are many possible formats, and you will have to look to the definition of the TP itself for that information. But as an example, the *IntKey* Transaction Processor uses a payload of three key/value pairs encoded as `CBOR <https://en.wikipedia.org/wiki/CBOR>`_. Creating one might look like this:
