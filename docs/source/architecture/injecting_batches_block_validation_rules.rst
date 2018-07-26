*****************************************************
Injecting Batches and On-Chain Block Validation Rules
*****************************************************

The validator can inject transactions into blocks. This functionality supports a
variety of use cases, such as:

- Setting information in state for use by transaction processors that cannot
  reasonably be provided with every transaction. For example, setting the block
  number or timestamp.
- Automatically submitting transactions in response to a particular state. For
  example, submitting bond-quote-matching transactions.
- Testing automation. For example, programming the compute time of test
  transactions to increase after a certain number of batches.

Sawtooth allows the validator to impose a set of rules on the relationships
between transactions, or inter-transaction validation. This is also required for
some use cases.  Two examples of inter-transaction validation are:

- Only N of transaction type X can be included in a block.
- Transaction type X can only occur at position Y in a block.

BatchInjector Interface
=======================

The ``BatchInjector`` class supports injecting transactions into blocks:

.. code-block:: python

  interface BatchInjector:
    // Called when a new block is created and before any batches are added. A list of
    // batches to insert at the beginning of the block must be returned. A StateView
    // is provided for inspecting state as of the previous block.
    block_start(string previous_block_id) -> list<Batch>

    // Called before inserting the incoming batch into the pending queue for the
    // given block. A list of batches to insert before this batch must be returned.
    before_batch(string previous_block_id, Batch batch) -> list<Batch>

    // Called after inserting the incoming batch into the pending queue for the
    // given block. A list of batches to insert after this batch must be returned.
    after_batch(string previous_block_id, Batch batch) -> list<Batch>

    // Called just before finalizing and completing a Block. An ordered list of batches
    // that will be committed in the block is passed in. A list of batches to insert at
    // the end of the block must be returned.
    block_end(string previous_block_id, list<Batch> batches) -> list<Batch>

The BlockPublisher (part of the :doc:`journal <../architecture/journal>`)
will call each of the methods at the appropriate times for all
included BatchInjectors, thus injecting batches into the new block.

On-Chain Configuration
======================

The set of BatchInjectors to load is configured with an on-chain setting; this
is similar to configuring the consensus module loaded by the validator.
The ``sawtooth.validator.batch_injectors`` setting key stores a comma-separated
list of batch injectors to load.  This list is parsed by the validator at the
beginning of block publishing for each block and the appropriate injectors are
loaded.

This setting is controlled using the existing
:doc:`Settings transaction family <../transaction_family_specifications/settings_transaction_family>`.
Take care when updating this setting, because an incorrect value may cause
transaction families to behave incorrectly.

On-Chain Validation Rules
=========================

An on-chain setting holds a set of validation rules that are enforced for
each block. On-chain validation rules are stored as a string in the setting
key ``sawtooth.validator.block_validation_rules``. Rules are enforced by the
block validator.

Validation rules use the following simple syntax:

- A validation rule consists of a name followed by a colon and a comma-separated
  list of arguments: ``rulename:arg,arg,...,arg``

- Separate multiple rules with semicolons:
  ``rulename1:arg,arg,...,arg;rulename2:arg,arg,...,arg``

- Spaces, tabs, and newlines are ignored.

The following rules are defined:

NofX
  Only N transaction of transaction type X may be included in a block. The first
  argument must be an integer. The second argument is the name of a transaction
  family. For example, the string
  ``NofX:2,intkey`` means allow only two IntegerKey transactions per block.

XatY
  A transaction of type X must be in the block at position Y. The first argument
  is interpreted as the name of a transaction family (``family_name``).
  The second argument must
  be interpretable as an integer and defines the index of the transaction in
  the block that must be checked. Negative numbers can be used and count
  backwards from the last transaction in the block. The first transaction in the
  block has index 0. The last transaction in the block has index -1. If abs(Y)
  is larger than the number of transactions per block, then there would not be
  a transaction of type X at Y and the block would be invalid. For example, the
  string ``XatY:intkey,0`` means the first transaction in the block must be an
  IntegerKey transaction.

local
  A transaction must be signed by the same key as the block. This rule takes a
  list of transaction indices in the block and enforces the rule on each. This
  rule is useful in combination with the other rules to ensure a client is not
  submitting transactions that should only be injected by the winning validator.

Example: BlockInfoInjector
==========================

The BlockInfoInjector inserts a BlockInfo transaction at the beginning of every
block. The transaction updates state with information about the block that was
just committed as well as a timestamp. For more information, see the
:doc:`BlockInfo Transaction Family
<../transaction_family_specifications/blockinfo_transaction_family>`.


The following validation rules are added to the set of on-chain validation rules
in order to prevent bad actors from injecting incorrect but valid BlockInfo
transactions. The rules require that only one BlockInfo transaction is included
per block, that the transaction is at the beginning of the block, and that the
transaction is signed by the same key that signed the block.

- NofX:1,block_info;
- XatY:block_info,0;
- local:0

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
