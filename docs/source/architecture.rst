
******************
Architecture Guide
******************

The following diagram shows a high-level view of the Sawtooth architecture.

This guide describes the design and architecture of Hyperledger Sawtooth,
an enterprise blockchain platform for building distributed ledger applications
and networks.

This guide starts by explaining the important concepts of :term:`global state`
and :term:`Sawtooth batches<Batch>`. Next, it describes key parts of the
:term:`validator` and other core features, including the journal for block
management, consensus, transaction scheduling, permissioning, and more.

.. figure:: images/arch-sawtooth-overview.*
   :width: 100%
   :align: center
   :alt: Sawtooth core architecture

.. toctree::
   :maxdepth: 2

   architecture/global_state
   architecture/transactions_and_batches
   architecture/journal
   architecture/scheduling
   architecture/rest_api
   architecture/validator_network
   architecture/permissioning_requirement
   architecture/injecting_batches_block_validation_rules
   architecture/events_and_transactions_receipts
   architecture/poet

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
