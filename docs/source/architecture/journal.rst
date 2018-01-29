*******
Journal
*******

The Journal is responsible for maintaining and extending the blockchain for the
validator. This responsibility involves validating candidate blocks, evaluating
valid blocks to determine if they are the correct chain head, and generating
new blocks to extend the chain.

The Journal is the consumer of Blocks and Batches that arrive at the validator.
These Blocks and Batches arrive via interconnect, either through the gossip
protocol or the REST API. The newly-arrived Blocks and Batches are sent to the
Journal, which routes them internally.

.. image:: ../images/journal_organization.*
   :width: 80%
   :align: center
   :alt: Journal Organization Diagram

The Journal divides up the processing of Blocks and Batches to different
pipelines. Both objects are delivered initially to the Completer, which
guarantees that all dependencies for the Blocks and Batches have been satisfied
and delivered downstream. Completed Blocks are delivered to the Chain
controller for validation and fork resolution. Completed Batches are delivered
the BlockPublisher for validation and inclusion in a Block.

The Journal is designed to be asynchronous, allowing incoming blocks to be
processed in parallel by the ChainController, as well as allowing the
BlockPublisher to proceed with claiming blocks even when the incoming block
rate is high.

It is also flexible enough to accept different consensus algorithms.  The
Journal implements a consensus interface that defines the entry points and
responsibilities of a consensus algorithm.

The BlockStore
==============

The BlockStore contains all the blocks in the current blockchain - that is, the
list of blocks from the current chain head back to the Genesis blocks. Blocks
from forks are not included in the BlockStore. The BlockStore also includes a
reference to the head of the current chain. It is expected to be coherent at
all times, and an error in the BlockStore is considered a non-recoverable error
for the validator. Such critical errors would include missing blocks, bad
indexes, missing chain reference, incomplete blocks or invalid blocks in the
store. The BlockStore provides an atomic means to update the store when the
current fork is changed (the chain head is updated).

The BlockStore is a persistent on-disk store of all Blocks in the current
chain. When the validator is started, the contents of the BlockStore is trusted
to be the current state of the world.

All blocks stored here are formally complete. The BlockStore allows blocks to
be accessed via Block ID. Blocks can also be accessed via Batch ID,
Transaction ID, or block number; for example, ``get_block_by_batch_id``,
``get_block_by_transaction_id``, ``get_batch_by_transaction``, or
``get_block_by_number``.

The BlockStore maintains internal mappings of Transaction-to-Block and
Batch-to-Block. These may be rebuilt if missing or corrupt. This rebuild should
be done during startup, and not during the course of normal operation. These
mappings should be stored in a format that is cached to disk, so they are not
required to be held in memory at all times. As the blockchain grows, these will
become quite large.

The BlockStore provides an atomic method for updating the current head of the
chain. In order for the BlockStore to switch forks, it is provided with a list
of blocks in the new chain to commit, and a list of blocks in the old chain to
decommit. These lists are the blocks in each fork back to the common root.

The BlockCache
==============

The Block Cache holds the working set of blocks for the validator and tracks the
processing state. This processing state is tracked as valid, invalid, or
unknown. Valid blocks are blocks that have been proven to be valid by the
ChainController. Invalid blocks are blocks that failed validation or have an
invalid block as a predecessor. Unknown are blocks that have not yet completed
validation, usually having just arrived from the Completer.

The BlockCache is an in-memory construct. It is rebuilt by demand when the
system is started.

If a block is not present in the BlockCache, it will look in the BlockStore for
the block. If it is not found or the lookup fails, the block is unknown to the
system. If the block is found in the BlockStore it is loaded into the
BlockCache and marked as valid. All blocks in the BlockStore are considered
valid.

The BlockCache keeps blocks that are currently relevant, tracked by the last
time the block was accessed. Periodically, the blocks that have not been
accessed recently are purged from the block cache, but only if none of the
other blocks in the BlockCache reference those blocks as predecessors.

The Completer
=============

The Completer is responsible for making sure Blocks and Batches are complete
before they are delivered. Blocks are considered formally complete once all of
their predecessors have been delivered to the ChainController and their batches
field contains all the Batches specified in the BlockHeader’s batch_ids list.
The batches field is also expected to be in the same order as the batch_ids.
Once Blocks are formally complete they are delivered to the ChainController for
validation.

Batches are considered complete once all of its dependent transactions exist in
the current chain or have been delivered to the BlockPublisher.

All Blocks and Batches will have a timeout for being completed. After the
initial request for the missing dependencies is sent, if the response is not
received within the specified time window, they are dropped.

If you have a new block of unknown validity, you must ensure that its
predecessors have been delivered to the journal. If a predecessor is not
delivered on request to the journal in a reasonable amount of time, the new
block cannot be validated.

Consider the case where you have the chain A->B->C :

If C arrives and B is not in the BlockCache, the validator will request B. If
the request for B times out, the C block is dropped.

If later on D arrives with predecessor C, of chain A->B->C->D, the Completer
will request C from the network and once C arrives, then will request B again.
If B arrives this time, then the new chain will be delivered to the
ChainController, where they will be check for validity and considered for
becoming the block head by the ChainController.

The Consensus Interface
=======================

In the spirit of configurability, the Journal supports
:term:`dynamic consensus algorithms<Dynamic consensus>`
that can be changed via the Settings transaction family. The
initial selection of a consensus algorithm is set for the chain in the genesis
block during genesis (described below). This may be changed during the course of
a chain's lifetime. The Journal and its consensus interface support dynamic
consensus for probabilistic finality algorithms like Proof of Work, as well as
algorithms with absolute finality like PBFT.

The Consensus algorithm services to the journal are divided into three distinct
interfaces that have specific lifetimes and access to information.

1. Consensus.BlockPublisher
2. Consensus.BlockVerifier
3. Consensus.ForkResolver

Consensus algorithm implementations in Sawtooth must implement all of the
consensus interfaces. Each of these objects are provided read-only access to
the BlockCache and GlobalState.

Consensus.BlockPublisher
------------------------

An implementation of the interface Consensus.BlockPublisher is used by the
BlockPublisher to create new candidate blocks to extend the chain. The
Consensus.BlockPublisher is provided access to a read-only view of global
state, a read-only view of the BlockStore, and an interface to publish batches.

Three events are called on the Consensus.BlockPublisher,

1. initialize_block - The BlockHeader is provided for the candidate block. This
   is called immediately after the block_header is initialized and allows for
   validation of the consensus algorithm's internal state, checks if the header
   is correct, checks if according to the consensus rules a block could be
   published, and checks if any initialization of the block_header is required.
   If this function fails no candidate block is created and the BlockPublisher
   will periodically attempt to create new blocks.
2. check_publish_block - Periodically, polling is done to check if the block can
   be published. In the case of PoET, this is a check to see if the wait time
   has expired, but could be on any other criteria the consensus algorithm has
   for determining if it is time to publish a block. When this returns true the
   BlockPublisher will proceed in creating the block.
3. finalize_block - Once check_publish_block has confirmed it is time to
   publish a block, the block header is considered complete, except for the
   consensus information. The BlockPublisher calls finalize_block with the
   completed block_header allowing the consensus field to be filled out.
   Afterwards, the BlockPublisher signs the block and broadcasts it to the
   network.

This implementation needs to take special care to handle the genesis block
correctly. During genesis operation, the Consensus.BlockPublisher will be called
to initialize and finalize a block so that it can be published on the chain
(see below).

Consensus.BlockVerifier
-----------------------

The Consensus.BlockVerifier implementation provides Block verification services
to the BlockValidator. This gives the consensus algorithm an opportunity to
check whether the candidate block was published following the consensus rules.

Consensus.ForkResolver
----------------------

The consensus algorithm is responsible for fork resolution on the system.
Depending on the consensus algorithm, the determination of the valid block to
become the chain head will differ. In a Bitcoin Proof of Work consensus, this
will be the longest chain, whereas PoET uses the measure of aggregate local
mean (a measure of the total amount of time spent waiting) to determine the
valid fork. Consensus algorithms with finality, such as PBFT, will only ever
produce blocks that extend the current head. These algorithms will never have
forks to resolve. The ForkResolver for these algorithms with finality will
always select the new block that extends the current head.

The ChainController
===================

The ChainController is responsible for determining which chain the validator is
currently on and coordinating any change-of-chain activities that need to
happen.

The ChainController is designed to be able to handle multiple block validation
activities simultaneously. For instance, if multiple forks form on the network,
the ChainController can process blocks from all of the competing forks
simultaneously. This is advantageous as it allows progress to be made even when
there are several deep forks competing. The current chain can also be advanced
while a deep fork is being evaluated. This was implemented for cases that could
happen if a group of validators lost connectivity with the network and later
rejoined.

.. note::

  Currently, the thread pool is set to 1, so only one Block is validated
  at a time.

Here is the basic flow of the ChainController as a single block is processed.

.. image:: ../images/journal_chain_controller.*
   :width: 80%
   :align: center
   :alt: Journal Chain Controller Diagram

When a block arrives, the ChainController creates a BlockValidator and
dispatches it to a thread pool for execution.  Once the BlockValidator has
completed, it will callback to the ChainController indicating whether the new
block should be the chain head. This indication falls into 3 cases:

1. The chain head has been updated since the BlockValidator was created. In
   this case a new BlockValidator is created and dispatched to redo the fork
   resolution.
2. The new Block should become the chain head. In this case the chain head is
   updated to be the new block.
3. The new Block should not become the chain head. This could be because the
   new Block is part of a chain that has an invalid block in it, or it is a
   member of a shorter or less desirable fork as determined by consensus.

The Chain Controller synchronizes chain head updates such that only one
BlockValidator result can be processed at a time. This is to prevent the race
condition of multiple fork resolution processes attempting to update the chain
head at the same time.

Chain Head Update
-----------------

When the chain needs to be updated, the ChainController does an update of the
ChainHead using the BlockStore, providing it with the list of commit blocks
that are in the new fork and a list of decommit blocks that are in the
BlockStore, which must be removed. After the BlockStore is updated, the Block
Publisher is notified that there is a new ChainHead.

Delayed Block Processing
------------------------

While the ChainController does Block validation in parallel, there are cases
where the ChainController will serialize Block validation. These cases are when
a Block is received and any of its predecessors are still being validated. In
this case the validation of the predecessor is completed before the new block is
scheduled. This is done to avoid redoing the validation work of the predecessor
Block, since the predecessor must be validated prior to the new Block, the delay
is inconsequential to the outcome.

The BlockValidator
------------------

The BlockValidator is a subcomponent of the ChainController that is responsible
for Block validation and fork resolution. When the BlockValidator is
instantiated, it is given the candidate Block to validate and the current chain
head.

During processing, if a Block is marked as invalid it is discarded, never to be
considered again. The only way to have the Block reconsidered is by flushing the
BlockCache, which can be done by restarting the validator.

The BlockValidator has three stages of evaluation.

1. Determine the common root of the fork (ForkRoot). This is done by walking the
   chain back from the candidate and the chain head until a common block is
   found. The Root can be the ChainHead in the case that the Candidate is
   advancing the existing chain. The only case that the ForkRoot will not be
   found is if the Candidate is from another Genesis. If this is the case, the
   Candidate and all of its predecessors are marked as Invalid and discarded.
   During this step, an ordered list of both chains is built back to the
   ForkRoot.
2. The Candidate chain is validated. This process walks forward from the
   ForkRoot and applies block validation rules (described below) to each Block
   successively. If any block fails validation, it and all of its successors
   are marked as Invalid (Valid Blocks are defined as having Valid
   predecessor(s)). Once the Candidate is successfully Validated and marked as
   Valid, the Candidate is ready for Fork Resolution.
3. Fork resolution requires a determination to be made if the Candidate should
   replace the ChainHead and is deferred entirely to the consensus
   implementation. Once the Consensus determines if the block is the new
   ChainHead, the answer is returned to the ChainController, which updates the
   BlockStore.  If it is not the new ChainHead, the Candidate is dropped.
   Additionally, if the Candidate is to become the ChainHead, the list of
   transactions committed in the new chain back to the common root is computed
   and the same list is computed on the current chain. This information helps
   the BlockPublisher update its pending batch list when the chain is updated.

Block Validation
----------------

Block validation has the following steps that are always run in order. Failure
of any validation step results in failure, processing is stopped, and the Block
is marked as Invalid.

1. **Transaction Permissioning** - On-chain transaction permissions are
   checked to see who is allowed to submit transactions and batches.

#. **On-chain Block Validation Rules** - The on-chain block validation rules
   are checked to ensure that the Block doesn't invalidate any of the
   rules stored at ``sawtooth.validator.block_validation_rules``.

#. **Batches Validation** - All of the Batches in the block are sent in order
   to a Transaction Scheduler for validation. If any Batches fail validation,
   this block is marked as invalid. Note: Batch and Signature verification is
   done on receipt of the Batch prior to it being routed to the Journal. The
   batches are checked for the following:

    * No duplicate Batches
    * No duplicate Transactions
    * Valid Transaction dependencies
    * Successful Batch Execution

#. **Consensus Verification** - The Consensus instance is given to the Block for
   verification. Consensus block verification is done by the consensus algorithm
   using its own rules.

#. **State Hash Check** - The StateRootHash generated by validating the block is
   checked against the StateRootHash (state_root_hash field in the BlockHeader)
   on the block. They must match for the block to be valid.

If the block is computed to be valid, then StateRootHash is committed to the
store.

The BlockPublisher
==================

The BlockPublisher is responsible for creating candidate blocks to extend the
current chain. The BlockPublisher does all of the housekeeping work around
creating a block but takes direction from the consensus algorithm for when to
create a block and when to publish a block.

The BlockPublisher follows this logic flow:

.. image:: ../images/journal_block_publisher_flow.*
   :width: 80%
   :align: center
   :alt: Journal Block Publisher Diagram

At each processing stage, the consensus algorithm has a chance to inspect and
confirm the validity of the block.

During CreateBlock, an instance of Consensus.BlockPublisher is created that is
responsible for guiding the creation of this candidate block.  Also, a
TransactionScheduler is created and all of the pending Batches are submitted to
it.

A delay is employed in the checking loop to ensure that there is time for the
batch processing to occur.

Genesis Operation
=================

The Journal supports Genesis operation. This is the action of creating a root of
the chain (the Genesis block) when the block store is empty. This operation is
necessary for bootstrapping a validator network with the desired consensus
model, any deployment-specific configuration settings, as well as any
genesis-time transactions for an application's Transaction Family.

Genesis Batch Creation
----------------------

The CLI tool produces batches in a file, which will be consumed by the
validator on startup (when starting with an empty chain).

The file contains a protobuf-encoded list of batches:

.. code-block:: protobuf
        :caption: File: sawtooth-core/protos/genesis.proto

        message GenesisData {
            repeated Batch batches = 1;
        }

The tool should take multiple input batch collections, and combine them
together into the single list of batches contained in GenesisData. This allows
independent tools or transaction families to include their own batches, without
needing to know anything about the genesis process.

The first implementation assumes that the order of the input batches have
implied dependencies, with each batch being implicitly dependent on the
previous.  Any dependencies should be verified when the final set of batches is
produced.  This would be enforced by the use of strict ordering of the batches
during execution time.  Future implementations may provide a way to verify
dependencies across input batches.

Transaction family authors who need to provide batches that will be included,
need to provide their own tool to produce GenesisData, with the batches they
require for the process. Each individual tool may manage their batch and
transaction dependencies explicitly within the context of their specific
genesis batches.

Example
~~~~~~~

The following example configures the validator to use PoET consensus
and specifies the appropriate settings:

.. code-block:: bash

        sawset proposal create \
          -k <signing-key-file> \
          -o sawset.batch \
          sawtooth.consensus.algorithm=poet \
          sawtooth.poet.initial_wait_timer=x \
          sawtooth.poet.target_wait_time=x \
          sawtooth.poet.population_estimate_sample_size=x
	  sawadm genesis \
          sawset.batch

A genesis.batch file will written to the validator's data directory.

Block Creation
--------------

On startup, the validator would use the resulting genesis.batch file to produce
a genesis block under the following conditions:

* The genesis.batch file exists
* There is no block specified as the chain head

If either of these conditions is not met, the validator halts operation.

The validator will load the batches from the file into the pending queue.  It
will then produce the genesis block through the standard process with the
following modifications.

First, the execution of the batches will be strictly in the order they have
been provided.  The Executor will not attempt to reorder them, or drop failed
transactions.  Any failure of a transaction in genesis.batch will fail to
produce the genesis block, and the validator will treat this as a fatal error.

Second, it will use a genesis consensus, to determine block validity. At the
start of the genesis block creation process, state (the Merkle-Radix tree) will be empty.
Given that the consensus mechanism is specified by a configuration setting in
the state, this will return None.  As a result, the genesis consensus mechanism
will be used. This will produce a block with an empty consensus field.

In addition to the genesis block, the blockchain ID (that is, the signature of
the genesis block) is written to the file ``block-chain-id`` in the validator’s
data directory.

Part of the production of the genesis block will require the configuration of
the consensus mechanism. The second block will then use the configured
consensus model, which will need to know how to initialize the consensus field
from an empty one.  In future cases, transitions between consensus models may be
possible, as long as they know how to read the consensus field of the previous
block.

To complete the process, all necessary transaction processors must be running.
A minimum requirement is the Sawtooth Settings transaction processor,
``settings-tp``.

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
