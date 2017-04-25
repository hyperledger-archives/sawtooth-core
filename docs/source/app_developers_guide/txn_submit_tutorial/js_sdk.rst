:orphan:

.. _txn-submit-tutorial-js-sdk:

.. include:: _segments/intro.rst


.. include:: _segments/keys_private.rst

It is fairly simple to generate this using the *signer* module.


.. code-block:: javascript

    const {signer} = require('sawtooth-sdk')

    const privateKey = signer.makePrivateKey()

.. include:: _segments/keys_private_info.rst

As the SDK automatically generates and sets a public key, there is no need to explictly create one.


.. include:: _segments/payload.rst

.. code-block:: javascript

    const cbor = require('cbor')

    const payload = {
        Verb: 'set',
        Name: 'foo',
        Value: 42
    }

    const payloadBytes = cbor.encode(payload)


.. include:: _segments/txn_create.rst


.. include:: _segments/sdk_txn1_encoder.rst

.. code-block:: javascript

    const {TransactionEncoder} = require('sawtooth-sdk')

    const encoder = new TransactionEncoder(privateKey, {
        familyName: 'intkey',
        familyVersion: '1.0',
        inputs: ['1cf126'],
        outputs: ['1cf126'],
        payloadEncoding: 'application/cbor'
        payloadEncoder: cbor.encode
    })


.. include:: _segments/header_info.rst


.. include:: _segments/sdk_txn2_create.rst

.. code-block:: javascript

    const txn = encoder.create(payload, {
        inputs: ['1cf12632a292f6ddf757a0a59e9c2284c08cab235aa068b19f85c460f71485540368eec98c3f95af23b0c8cda4790c118238a3b97f2fba2bbff72f15987f00b41e7caf'],
        outputs ['1cf12632a292f6ddf757a0a59e9c2284c08cab235aa068b19f85c460f71485540368eec98c3f95af23b0c8cda4790c118238a3b97f2fba2bbff72f15987f00b41e7caf']
    })

    const txn2 = encoder.create({
        Verb: 'inc',
        Name: 'foo',
        Value: 1
    })


.. include:: _segments/sdk_txn3_encode.rst

.. code-block:: javascript

    const txnBytes = encoder.encode([txn1, txn2])

    const txnBytes2 = encoder.createEncoded({
        Verb: 'dec',
        Name: 'foo',
        Value: 3
    })


.. include:: _segments/batch_create.rst


.. include:: _segments/sdk_batch1_encoder.rst

.. code-block:: javascript

    const {BatchEncoder} = require('sawtooth-sdk')

    const batcher = new BatchEncoder(privateKey)


.. include:: _segments/sdk_batch2_create.rst

.. code-block:: javascript

    const batch = batcher.create(txnBytes)

    const batch2 = batcher.create(txn)


.. include:: _segments/sdk_batch3_encode.rst

.. code-block:: javascript

    const batchBytes = batcher.encode([batch, batch2])

    const batchBytes2 = batcher.createEncoded(txnBytes)


.. include:: _segments/submit.rst

.. code-block:: javascript

    const request = require('request')

    request.post({
        url: '127.0.0.1:8080/batches',
        body: batchBytes,
        headers: {'Content-Type': 'application/octet-stream'}
    }, (err, response) => {
        . . .
    })


.. include:: _segments/submit_curl.rst

.. code-block:: javascript

    const fs = require('fs')

    const fileStream = fs.createWriteStream('intkey.batches')
    fileStream.write(batchBytes)
    fileStream.end()

.. code-block:: bash

    % curl -X POST \
        -H "Content-Type: application/octet-stream" \
        --data-binary "intkey.batches" \
        http://127.0.0.1:8080/batches
