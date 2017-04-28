:orphan:

.. _txn-submit-tutorial-js:

.. include:: _segments/intro.rst


.. include:: _segments/keys_private.rst

A common way to generate one is to create a random set of bytes, and then use a secp256k1 library to ensure they are valid.

.. code-block:: javascript

    const crypto = require('crypto')
    const secp256k1 = require('secp256k1')

    let privateKeyBytes

    do {
        privateKeyBytes = crypto.randomBytes(32)
    } while (!secp256k1.privateKeyVerify(privateKeyBytes))

.. include:: _segments/keys_private_info.rst


.. include:: _segments/keys_public.rst

.. code-block:: javascript

    const publicKeyBytes = secp256k1.publicKeyCreate(privateKeyBytes)

    const publicKeyHex = publicKeyBytes.toString('hex')


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


.. include:: _segments/txn1_payload_hash.rst

.. code-block:: javascript

    const crypto = require('crypto')
    const sha512 = crypto.createHash('sha512')

    const payloadSha512 = sha512.update(payloadBytes).digest('hex')


.. include:: _segments/txn2_header.rst

.. code-block:: javascript

    const protobuf = require('protobufjs')

    const txnRoot = protobuf.loadSync('protos/transactions.proto')
    const TransactionHeader = txnRoot.lookup('TransactionHeader')

    const txnHeaderBytes = TransactionHeader.encode({
        batcherPubkey: publicKeyHex,
        dependencies: [],
        familyName: 'intkey',
        familyVersion: '1.0',
        inputs: ['1cf126'],
        nonce: Math.random().toString(36),
        outputs: ['1cf126'],
        payloadEncoding: 'application/cbor',
        payloadSha512: payloadSha512,
        signerPubkey: publicKeyHex
    }).finish()


.. include:: _segments/header_info.rst


.. include:: _segments/txn3_sign.rst

.. code-block:: javascript

    const sha256 = crypto.createHash('sha256')
    const txnHeaderHash = sha256.update(txnHeaderBytes).digest()

    const txnSigBytes = secp256k1.sign(txnHeaderHash, privateKey).signature
    const txnSignatureHex = txnSigBytes.toString('hex')


.. include:: _segments/txn4_create.rst

.. code-block:: javascript

    const Transaction = txnRoot.lookup('Transaction')

    const txn = Transaction.create({
        header: txnHeaderBytes,
        headerSignature: txnSignatureHex,
        payload: payloadBytes
    })


.. include:: _segments/txn5_encode.rst

.. code-block:: javascript

    const TransactionList = txnRoot.lookup('TransactionList')

    const txnBytes = TransactionList.encode({
        transactions: [txn]
    }).finish()


.. include:: _segments/batch_create.rst


.. include:: _segments/batch1_decode.rst

.. code-block:: javascript

    const txnList = TransactionList.decode(txnBytes)

    const txn = txnList.transactions[0]


.. include:: _segments/batch2_header.rst

.. code-block:: javascript

    const batchRoot = protobuf.loadSync('protos/batches.proto')
    const BatchHeader = batchRoot.lookup('BatchHeader')

    const batchHeaderBytes = BatchHeader.encode({
        signerPubkey: publicKey,
        transactionIds: [txn.headerSignature]
    }).finish()


.. include:: _segments/batch3_sign.rst

.. code-block:: javascript

    const batchHeaderHash = sha256.update(batchHeaderBytes).digest()
    const batchSignature = secp256k1.sign(batchHeaderHash, privateKey)


.. include:: _segments/batch4_create.rst

.. code-block:: javascript

    const Batch = batchRoot.lookup('Batch')

    const batch = Batch.create({
        header: batchHeaderBytes,
        headerSignature: batchSignature,
        transactions: [txn]
    })


.. include:: _segments/batch5_encode.rst

.. code-block:: javascript

    const BatchList = batchRoot.lookup('BatchList')

    const batchBytes = BatchList.encode({
        batches: [batch]
    }).finish()


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

    % curl -X POST
        -H "Content-Type: application/octet-stream" \
        --data-binary "intkey.batches" \
        http://127.0.0.1:8080/batches
