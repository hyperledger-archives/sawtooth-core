.. _txn-submit-tutorial-python:

.. include:: _segments/intro.rst


.. include:: _segments/keys_private.rst

The Python *secp256k1* module provides a *PrivateKey* handler class from which we can get the actual bytes to use for a key.

.. code-block:: python

    import secp256k1

    key_handler = secp256k1.PrivateKey()
    private_key_bytes = key_handler.private_key

.. include:: _segments/keys_private_info.rst


.. include:: _segments/keys_public.rst

.. code-block:: python

    public_key_bytes = key_handler.pubkey.serialize()

    public_key_hex = public_key_bytes.hex()


.. include:: _segments/payload.rst

.. code-block:: python

    import cbor

    payload = {
        'Verb': 'set',
        'Name': 'foo',
        'Value': 42}

    payload_bytes = cbor.dumps(payload)


.. include:: _segments/txn_create.rst


.. include:: _segments/txn1_payload_hash.rst

.. code-block:: python

    from hashlib import sha512

    payload_sha512 = sha512(payload_bytes).hexdigest()


.. include:: _segments/txn2_header.rst

.. code-block:: bash

    % protoc --python-out=compiled_protos/ protos/transactions.proto

.. code-block:: python

    from random import randint
    from compiled_protos.transactions_pb2 import TransactionHeader

    txn_header = TransactionHeader(
        batcher_pubkey=public_key_hex,
        dependencies=[],
        family_name='intkey',
        family_version='1.0',
        inputs=['1cf126'],
        nonce=str(randint(0, 1000000000)),
        outputs=['1cf126'],
        payload_encoding='application/cbor',
        payload_sha512=payload_sha512,
        signer_pubkey=public_key_hex)

    txn_header_bytes = txn_header.SerializeToString()


.. include:: _segments/header_info.rst


.. include:: _segments/txn3_sign.rst

.. code-block:: python

    key_handler = secp256k1.PrivateKey(private_key)

    # No need to manually generate a SHA-256 hash of the header
    txn_signature_bytes = key_handler.ecdsa_sign(txn_header_bytes)
    txn_signature_hex = txn_signature_bytes.hex()


.. include:: _segments/txn4_create.rst

.. code-block:: python

    from compiled_protos.transactions_pb2 import Transaction

    txn = Transaction(
        header=txn_header_bytes,
        header_signature=txn_signature_hex,
        payload=payload_bytes)


.. include:: _segments/txn5_encode.rst

.. code-block:: python

    from compiled_protos.transactions_pb2 import TransactionList

    txnList = TransactionList(transactions=[txn])
    txnBytes = txnList.SerializeToString()


.. include:: _segments/batch_create.rst


.. include:: _segments/batch1_decode.rst

.. code-block:: python

    txnList = TransactionList()
    txnList.ParseFromString(txnBytes)

    txn = txnList.transactions[0]


.. include:: _segments/batch2_header.rst

.. code-block:: bash

    % protoc --python-out=compiled_protos/ protos/batches.proto

.. code-block:: python

    from compiled_protos.batches_pb2 import BatchHeader

    batch_header = BatchHeader(
        signer_pubkey=public_key_hex,
        transaction_ids=[txn.header_signature])

    batch_header_bytes = batch_header.SerializeToString()


.. include:: _segments/batch3_sign.rst

.. code-block:: python

    batch_signature_bytes = key_handler.ecdsa_sign(batch_header_bytes)
    batch_signature_hex = batch_signature_bytes.hex()


.. include:: _segments/batch4_create.rst

.. code-block:: python

    from compiled_protos.batches_pb2 import Batch

    batch = Batch(
        header=batch_header_bytes,
        header_signature=batch_signature_hex,
        transactions=[txn])


.. include:: _segments/batch5_encode.rst

.. code-block:: python

    from compiled_protos.batches_pb2 import BatchList

    batch_list = BatchList(batches=[batch])
    batch_bytes = batch_list.SerializeToString()


.. include:: _segments/submit.rst

.. code-block:: python

    import urllib

    request = urllib.Request(
        '127.0.0.1:8080/batches',
        batch_bytes,
        method='POST',
        headers={'Content-Type': 'application/octet-stream'})

    response = urllib.urlopen(request)


.. include:: _segments/submit_curl.rst

.. code-block:: python

    output = open('batches.intkey', 'wb')
    output.write(batch_bytes)

.. code-block:: bash

    % curl -X POST \
        -H "Content-Type: application/octet-stream" \
        --data-binary "intkey.batches" \
        http://127.0.0.1:8080/batches
