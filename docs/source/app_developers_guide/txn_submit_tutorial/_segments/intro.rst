************************************
Building and Submitting Transactions
************************************

.. raw:: html
   :file: language_select.html

|

In the Sawtooth distributed ledger, *Transactions* are the method by which changes to state are declared and formatted. These Transactions are wrapped in *Batches* (the atomic unit of change in Sawtooth's blockchain) to be submitted to a validator. Each step in constructing these Transactions and Batches involves various cryptographic safeguards (SHA-256 and SHA-512 hashes, secp256k1 signatures), which can be daunting to those not already knowledgable of the core concepts. This document will take developers step by step through the process of building and submitting Transactions. Before beginning, make sure you are familiar with structure of :doc:`/architecture/transactions_and_batches`, especially the various components of a *TransactionHeader*.

.. note::

   This document includes example code in a few different languages, as well as Sawtooth's SDKs. If available, it is recommended app developers use the SDK of their chosen language to build and submit Transactions, as it greatly simplifies the process.

   If you need to build Transactions manually, the non-SDK code provides concrete examples of each step. Use the drop down above to select the language you would prefer to see these examples in.