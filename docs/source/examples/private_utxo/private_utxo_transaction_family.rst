***************************************
Private UTXO Transaction Family
***************************************

Overview
========

This document describes a Transaction Family that allows for assets to be
tracked and traded on the Ledger as well as to be held off the Ledger. This
off-Ledger processing allows assets to be traded in a a  manner that enforces
the Ledger rules governing the Asset and allows transactional privacy for the
owner of the asset.

When assets are on-Ledger they are held in buckets associated with the owner’s
public key. In this state the balances and trades of and trades between
participants are visible to all who can see the Ledger. The second state of
assets is off-Ledger, as unspent transaction outputs (UTXO). In this form the
assets are represented as documents stored off-Ledger and the UTXO are opaque
identifiers of these documents stored in the Ledger. Trusted Execution
Environments(TEE) are used to validate and process off Ledger transactions.
Once validated by the TEE, the transaction is submitted to the Ledger recording
the UTXO consumed and the new UTXO produced.

State
=====

This section describes in detail how Private UTXO Transaction Processor (PUTP)
objects are stored and addressed in the global state. All objects in state are
stored as encoded protobufs. The address of the Merkle nodes is detailed below
in the addressing section.

AssetType
---------

AssetTypes represent types of assets being tracked and traded on the Ledger.

.. literalinclude:: ../../../../families/private_utxo/protos/asset_type.proto
    :language: protobuf
    :lines: 18-

Holding
-------

Holdings represent the amount of an assets a participant possesses on the
Ledger. This handles the unlikely case of collisions due to the transformation
of multiple public keys to the same address in global state.

The state entry for holdings is a container that allows the holdings of
multiple participants to be stored at the same address. This handles the
unlikely case of collisions due to the transformation of multiple public keys
to the same address in global state. The Holding container is a list of
participant holdings. Each holding is identified by the participant's public
key.

The participant Holding is a list of key value pairs, with the key being the
AssetType address and the value being the amount of the asset the participant
has.

.. literalinclude:: ../../../../families/private_utxo/protos/holding.proto
    :language: protobuf
    :lines: 22-

UTXO
----

UTXO are stored in the state, The key uniquely identifies the UTXO. Since there
is no value associated with UTXO, the Key is stored as the value. The value and
details of the UTXO are described by the UtxoDocument held off chain.


Addressing
----------

The PUTP uses the standard Sawtooth Merkle Addressing scheme a of 70 byte hex
encoded string, consisting of 6 characters of namespace and 64 characters of
key.

Asset Type Addresses
++++++++++++++++++++

AssetTypes are stored in the address type namespace: '87f09c', which is derived
by hex encoding the first 3 bytes of the sha512 hash of the string
'private_utxo.asset_types'.

.. code-block:: python

    >>> asset_namespace = hashlib.sha512("private_utxo.asset_types".encode())\
    ... .hexdigest()[0:6]
    >>> asset_namespace
    '87f09c'

AssetType addresses are derived from the contents of the create transaction.
The name, issuer's hex encoded public key, and the nonce are concatenated and
the sha512 hash is taken. The result is hex encoded and the first 64 bytes of
the result are taken as the address.

.. code-block:: python

    >>> raw_key = name + issuer_public_key + nonce
    >>> address = hashlib.sha512(raw_key.encode()).hexdigest()[0:64]


Holding Addresses
+++++++++++++++++

Holdings are stored in the address type namespace: 'f1fc42', which is derived
by hex encoding the first 3 bytes of the sha512 hash of the string
'private_utxo.holdings'.

.. code-block:: python

    >>> holdings_namespace = hashlib.sha512("private_utxo.holdings".encode())\
    ... .hexdigest()[0:6]
    >>> holdings_namespace
    'f1fc42'

Holding addresses are derived from the participant's public key. The sha512
hash is taken of the participants hex encoded public key. The result is hex
encoded and the first 64 bytes of the result are taken as the address.

.. code-block:: python

    >>> address = hashlib.sha512(public_key.encode()).hexdigest()[0:64]


UTXO Addresses
++++++++++++++

UTXOs are stored in the address type namespace: 'cbefaf', which is derived by
hex encoding the first 3 bytes of the sha512 hash of the string
'private_utxo.utxo'.

.. code-block:: python

    >>> utxo_namespace = hashlib.sha512("private_utxo.utxo".encode())\
    ... .hexdigest()[0:6]
    >>> utxo_namespace
    'cbefaf'

UTXOs addresses are derived from the UtxoDocument. The sha512 hash is taken of
the UtxoDocument. The result is hex encoded and the first 64 bytes of the
result are taken as the address.

.. code-block:: python

    >>> address = hashlib.sha512(utxo_document).hexdigest()[0:64]


Transactions
============

Transaction Headers
-------------------

The settings for the common Sawtooth Transaction header fields:

.. code-block:: javascript

    {
        family_name: "sawtooth_private_utxo"
        family_version: "1.0"
        encoding: "application/protobuf"
    }

Inputs and Outputs
------------------

Issue Asset
+++++++++++

    Inputs:

    * AssetType Address of the asset being issued

    Outputs:

    * AssetType Address of the asset being issued
    * Holding Address of the transaction signer

Transfer Asset
++++++++++++++

    Inputs:

    * AssetType Address of the asset being transfered
    * Holding Address of the transaction signer
    * Holding Address of the recipient

    Outputs:

    * Holding Address of the transaction signer
    * Holding Address of the recipient

Convert To UTXO
+++++++++++++++

    Inputs:

    * AssetType Address of the asset being converted
    * Holding Address of the transaction signer

    Outputs:

    * Holding Address of the transaction signer
    * The output UTXO address

Convert From UTXO
+++++++++++++++++

    Inputs:

    * AssetType Address of the asset being converted
    * Holding Address of the transaction signer
    * The UTXO address of the UtxoDocument

    Outputs:

    * Holding Address of the transaction signer
    * The UTXO address of the UtxoDocument

Transfer UTXO
+++++++++++++++++

    Inputs:

    * Settings address for `sawtooth.private_utxo.valid_enclave_measurements`
    * The all of the input and output UTXO addresses

    Outputs:

    * The all of the input and output UTXO addresses

Dependencies
++++++++++++

Transactions should be batched and should specify any transactions that they
expect to be committed to the ledger prior to execution as dependencies.

Transaction Payload
===================

All Private UTXO transactions are wrapped in a payload object that allows for
the items to be dispatched to the correct handling logic.


.. literalinclude:: ../../../../families/private_utxo/protos/payload.proto
    :language: protobuf
    :lines: 22-


Execution
=========

Holdings
--------

Participant Holdings are created when written to. If a Participants holdings
are being read and the Holding for that participant does not exist, the
particpant's holding of that asset are zero.

Issue Asset
-----------

**Issue Asset** transactions create new assets for trading. This can either be
in the form of creating a new AssetType entry or adding to the amount of an
existing asset in circulation.

**Issue Asset** transactions are validated as follows:

The address of the AssetType and the signer of the transaction are calculated.

If the AssetType exists and the AssetType issuer is the signer, then the
amount of the AssetType and the signers holdings for that AssetType are
increased by the transaction amount.

If the AssetType exists but the signer is not the issuer of the AssetType, the
transaction is invalid. These failures may be caused by collisions in the
AssetType address. If a transaction creates an AssetType that already exists
then it is an invalid transaction. In this case, the create AssetType
transactions should be recreated with a new nonce and resubmitted.

If the AssetType does not exist, then the AssetType is created with the Amount
from the transaction and the signers holdings for that AssetType are set to
the transaction amount.


Transfer Asset
--------------

**Transfer Asset** transactions are used to move assets from one participant's
holdings to another participant's holdings.

**Transfer Asset** transactions are validated as follows:

The signer of the transaction is calculated.

If the `asset_type` of the transaction does not exist, the transaction fails.
If the signer's holdings of the asset type are less than the transaction
amount, the transaction fails.

If the above validation steps pass, then the transaction amount is removed from
the signers holdings and added to the transaction recipients holdings.


Convert To UTXO
---------------

**Convert To UTXO** transactions are used to move assets from ledger holdings
to an off-Ledger UtxoDocument for private trading.

**Convert To UTXO** transactions are validated as follows:

The signer of the transaction is calculated.

If the `asset_type` of the transaction does not exist, the transaction fails.

If the signer's holdings of the `asset_type` are less than the transaction
amount the transaction fails.

The UtxoDocument is created with the signer as the document owner, and
the asset_type, amount, and nonce from the transaction. The UtxoDocument
address is computed and compared to the transactions output_utxo field. If
the addresses do not match, the transaction fails. UTXO collisions are not
allowed. If a transaction on UTXO creates a UTXO that already exists, it is an
invalid transaction. In this case the UtxoDocument should be recreated with a
new nonce and the transaction should be recreated.

If the above validation steps pass, then the transaction amount is removed from
the signer's holdings and the transaction `output_utxo` address is added
to the UTXO store.

Convert From UTXO
-----------------

**Convert From UTXO** transactions are used to move off-Ledger assets held in
UtxoDocuments to on-Ledger holdings.

**Convert From UTXO** transactions are validated as follows:

The signer of the transaction is calculated. The transaction document is
unpacked. The UtxoDocument address of the transaction document is calculated.

If the UtxoDocument address does not exist, the transaction fails.

If the `asset_type` of the document does not exist, the transaction fails. This
is done to ensure system consistency.

If the above validation steps pass, then the document amount is added to
the signer's holdings and the UtxoDocument address is removed
from the UTXO store.

Transfer UTXO
-----------------

**Transfer UTXO** transactions to facilitate off-Ledger trading.

**Transfer UTXO** transactions are validated as follows:

The transaction `attestation` is validated:

* If the attestation is not signed by IAS, the transaction fails
* If the attestation's `mr_enclave` is not the
  `sawtooth.private_utxo.valid_enclave_measurements`, the transaction fails.
* The attestation's report data (`sgx_report_data_t`) does not match the
  sha512(input|output), the transaction fails.

All input UTXO in the transaction must exist in the UTXO Store or the
transaction fails.

UTXO collisions are not allowed. If any of the UTXO outputs exist, then the
transaction fails. In this case, the output UtxoDocument should be recreated
with a new nonce and the transaction should be recreated.

If the above validation steps pass, then the transaction inputs are removed
from the UTXO store and the transaction outputs are added to the UTXO store.
