********************
Private UTXO Example
********************

This example shows how assets may be created and traded on the Sawtooth Ledger
and how SGX may be utilized to allow for assets to be transfered off ledger and
traded in private between parties with only the trading parties knowing the
details of the transaction.

The Private UTXO example allows for assets to be tracked and traded on the
Ledger. These assets can also be held off the Ledger and still traded in a
manner that enforces the Ledger rules governing the Asset and allows
transactional privacy for the owner of the asset. Assets in this system can
exist in two states; on-Ledger and off-Ledger. When assets are on-Ledger, they
are held in "Holdings" associated with the owner’s public key. In this state
the balances and trades of and trades between participants are visible to all
who can see the Ledger.

Assets
------

Assets in the off-Ledger state are unspent transaction outputs (UTXO) stored on
the Ledger with a matching document held by the owner off-Ledger describing the
Asset represented by the UTXO. Trusted Execution Environments(TEE) are used to
validate and process off-Ledger transactions. Once validated by the TEE, a
proof of the transaction is submitted to the Ledger recording the UTXO consumed
and the new UTXO produced.

Assets represent something of value. In order to preserve this value, it is
important that the rules governing that asset are preserved. In this system,
users can issue assets, but only the original issuer can create more. All other
transactions for these Assets can not change the amount of these Assets in
circulation.

In this example, Assets are represented as positive whole numbers. Fractional
asset representations are not supported.

The Private UTXO example manages three stores of information: the Asset Types,
Holdings, and UTXO. Participants may act on these stores according to their
permissions. Participants are identified by their public key. A Participant's
signature on a transaction is their authorization of the transaction.

Asset Types
+++++++++++

The Asset Type is the definition of what exists, who created it, and how much
of that asset is in circulation. The creator of the Asset Type may create more
of that asset at any time to increase the amount in circulation.

Holdings
++++++++

Holdings keep a record of which participants hold how much of which Assets.
Holdings can be thought of as on-Ledger wallets or bank accounts where the
balance of each Asset is held.

Unspent Transaction Output (UTXO)
+++++++++++++++++++++++++++++++++

When off-Ledger, the assets are represented as a document. This document
holds the details of the assets. The sha512 hash of this document is the UTXO
handle. In this case, the document is in a very real sense the asset that is
being represented. Having access to the document will provide the details of
the asset and who owns it. As such, it is important that the document is kept
secret and protected.  UTXODocument is considered valid when there is a
matching UTXO record in the DLT. If there is not a matching entry in the DLT
then the Asset has either been consumed or has not yet be recorded with
**Convert to UTXO** or **Transfer UTXO** transactions.


.. literalinclude:: ../../../../families/private_utxo/protos/utxo_document.proto
    :language: protobuf
    :lines: 18-25

Trading and Transactions
-------------------------

Private UTXO Transaction Family
+++++++++++++++++++++++++++++++

The Private UTXO Transaction Family is implemented by a Transaction Processor
that manages representation in the Ledger.
See :doc:`private_utxo_transaction_family` for more information.


Off-Ledger Trading
++++++++++++++++++

This section describes how off-Ledger Assets, stored in UTXODocuments,
are traded.

UTXO processing Trusted Execution Environment (UTEE) are responsible for
validating and signing all off-Ledger transactions. UTEE's will be provided as
signed binaries from the operators of the Ledger. The initial versions of the
UTEE will support operation on clients enabled with SGX technology. The UTEE
will utilize an IAS Proxy service to allow for generation of the Attestation
Verification Reports (AVRs).

The UTEE is responsible for enforcing the Asset semantic rules. This
implementation only enforces the constant supply of Assets (Transfers neither
create nor destroy assets). Other semantics are possible but would require a
different UTEE implementation to enforce those rules.

The flow of an off-Ledger trade happens as follows:

First, the UTXODocument owner creates a set of Output documents that they wish
to transform their document into. For example, if Alice has a UTXODocument for
100 units and wishes to give 10 to Bob, she would generate two output
UTXODocuments, one with Bob as the owner with the amount of 10 and the other
with her as the owner and the amount of 90.

Next, Alice will produce a signature of her input UTXODocument using her
private key. This signature acts as her authorization to consume the document.

The Input UTXODocument, the signature, and the output UTXODocuments are all
submitted to the UTEE for verification. When the verification finishes, a Quote
is generated by the UTEE. A Quote contains the details of the UTEE environment,
the enclave, and the transaction. The Quote is used by the Attestation service
to verify that this is a valid UTEE environment.

Alice then submits the Quote to the Intel Attestation Service for verification.
When the verification succeeds, an Attestation Verification Report (AVR) is
generated.

Alice will then generate a Transfer UTXO transaction with the addresses of the
input UTXODocument, the addresses of the output UTXODocuments, and the AVR. She
will sign this with a randomly generated key and submit it to any validator on
the network. A random signing key is used on these transactions so that the
transaction can not be traced back to the sender directly, providing anonymity
of who is participating in the transaction.

Once the Transfer UTXO transaction has been validated and is included in the
Ledger (added to a block in the block chain), the input UTXODocument is now
consumed and no longer valid, and the two output UTXODocuments are now valid.
Alice can now send the Output document to Bob and Bob can verify that they are
valid by seeing that the address of the document appears on the Ledger.

UTEE Enclave Operations
+++++++++++++++++++++++

The UTEE provides functionality to generate an Attestation for UTXO transfers.

Generate Transfer UTXO Quote
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Given a set of Input and Output UTXODocuments, validate the Inputs are
authorized to be spent and the Outputs conform to the asset rules. Then
generate a Quote attesting to the transfer's correctness.

Inputs:

* List of (UTXODocument, signature) pairs, specifying the UTXO inputs to spend
  and the authorization to spend them. The signatures are ECDSA signatures
  of UTXODocument, produced using the document owner's private key.
* List of Output UTXODocument.

Outputs:

* An Enclave quote (sgx_quote_t) with the report data set to
  (sgx_report_data_t) sha512(input UTXOs|output UTXOs)

Enclave Execution:

The enclave validates the following cases:

* The Input documents are validly formatted.
* The Output documents are validly formatted.
* All Inputs and outputs are of the same AssetType.
* The signatures match the owner in the corresponding Input UTXODocument.
* The sum of the outputs amounts equal the sum of the Input amounts.

If any of these cases are not true, the enclave stops processing and returns an
error.

If all the validation passes, then an enclave quote is generated. The report
data field of the quote (sgx_report_data_t) set to the sha512(input
addresses|output addresses). This provides linkage between the transaction and
the SGX Attestation. The input and output addresses are generated UTXO
address as described in the :doc:`private_utxo_transaction_family` .

IAS Proxy
^^^^^^^^^

Once the Enclave Quote is generated, it must be passed to the Intel Attestation
Service (IAS) for verification and signing. A proxy interface to IAS is
provided to allow the connection to IAS to be authenticated with the Software
provider Id. The proxy accepts the Enclave quotes and returns Attestation
Verification Reports (AVRs) signed by IAS.

Transfer UTXO Transaction
^^^^^^^^^^^^^^^^^^^^^^^^^

Once the Transfer AVR is created, a Transfer UTXO transaction can be created
and submitted for validation. This transaction must contain the input and
output document addresses in the order of the documents we submitted to the
UTEE. This transaction should be signed with a randomly generated key, so that
the identity of the UTXO can be hidden.

UTEE Authorization
^^^^^^^^^^^^^^^^^^

A Ledger setting in the settings namespace is used to hold the list of enclave
builds that are authorized to operate on this network. The setting
`sawtooth.private_utxo.valid_enclave_measurements` holds a comma separated list
of the measurements of enclaves that are allowed to attest for Transfer UTXO
transactions.

Best Practices
==============

The conversion of assets to and from the Ledger are visible and the spending
DAG of the off-Ledger UTXO is visible (note: the contents of the UTXO are
not visible). The UTXO DAG can provide an inadvertent source of information for
those interested in the trading behavior.

It is recommended that Participants in the system manage multiple private keys
for holding off-Ledger UTXO. Only use a primary key for trading on-Ledger and
have a set of keys for off-Ledger trading. When an asset is converted to UTXO,
it should be transferred among these keys several times in a random order to
hide the ownership of the asset. Furthermore, when an asset is transferred
off-Ledger, it should receive the same mixing behavior both before and after the
trade by both the sender and receiver. In addition, the off-Ledger keys should
regularly be regenerated so that the public keys cannot be associated with a
particular participant over time from observing the behavior of the trading.
