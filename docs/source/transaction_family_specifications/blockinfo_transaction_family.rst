****************************
BlockInfo Transaction Family
****************************

Overview
========

A common feature among blockchain implementations is the ability to reference
information about the blockchain while processing transactions. For example,
the Ethereum Virtual Machine, which is used to process Ethereum transactions,
defines a BLOCKHASH instruction which gives the processor executing the
transaction access to the hashes of previous blocks.

The Blockinfo transaction family provides a way for storing information about
a configurable number of historic blocks.

.. note::

   BlockInfo transactions should only be added to a block by a BlockInfo
   Injector and validation rules should ensure that only one transaction of this
   type is included at the beginning of the block. For more information,
   see :doc:`Injecting Batches and On-Chain Block Validation Rules
   <../architecture/injecting_batches_block_validation_rules>`.
   It is important to note that the data written to state by this
   transaction family cannot be trusted unless both the injector and
   validation rules are enabled.

State
=====
This section describes in detail how block information is stored and addressed
using the blockinfo transaction family.

Address
-------

The top-level namespace of this transaction family is 00b10c. This namespace is
further subdivided based on the next two characters as follows:

00b10c01
  Information about the block info config and metadata; the "metadata namespace"
00b10c00
  Historic block information; the "block info namespace"

Under the metadata namespace, the “zero-address” formed by concatenating the
namespace and enough zeros to form a valid address will store the
BlockInfoConfig.

Additional information about blocks will be stored in state under the block info
namespace at an address derived from the block number. A mod is used in the
calculation of the address to support chains that have a length greater than
the biggest number that can be hex-encoded with 62 characters. The procedure is
as follows:

  1. Convert block_num to a hex string and remove the leading “0x”
  2. Left pad the string with 0s until it is 62 characters long
  3. Concatenate the block info namespace and the string from step 3

For example, in Python the address could be constructed with:

.. code-block:: pycon

  >>> '00b10c00' + hex(block_num)[2:].zfill(62))

BlockInfo
---------

BlockInfoConfig will store the following information:

  - The block number of the most recent block stored in state
  - The block number of the oldest block stored in state
  - The target number of blocks to store in state
  - The network time synchronization tolerance

These values will be stored in the following protobuf message:

.. code-block:: protobuf

  message BlockInfoConfig {
    uint64 latest_block = 1;
    uint64 oldest_block = 2;
    uint64 target_count = 3;
    uint64 sync_tolerance = 4;
  }


Block information is stored at the address calculated above using the
following protobuf message:

.. code-block:: protobuf

  message BlockInfo {
    // Block number in the chain
    uint64 block_num = 1;

  	// The header_signature of the previous block that was added to the chain.
  	string previous_block_id = 2;

  	// Public key for the component internal to the validator that
  	// signed the BlockHeader
  	string signer_public_key = 3;

  	// The signature derived from signing the header
  	string header_signature = 4;

  	// Approximately when this block was committed, as a Unix UTC timestamp
  	uint64 timestamp = 5;
  }

Transaction Payload
===================

BlockInfo transaction family payloads are defined by the following protocol
buffers code:

.. code-block:: protobuf

  message BlockInfoTxn {
    // The new block to add to state
    BlockInfo new_block = 1;

    // If this is set, the new target number of blocks to store in state
    uint64 target_count = 2;

    // If set, the new network time synchronization tolerance.
    uint64 sync_tolerance = 3;
  }



Transaction Header
===================

Inputs and Outputs
------------------
The inputs for BlockInfo family transactions must include:

- the address of the BlockInfoConfig
- the BlockInfo namespace

The outputs for BlockInfo family transactions must include:

- the address of the BlockInfoConfig
- the BlockInfo namespace

Dependencies
------------
None.

Family
------

- family_name: "block_info"
- family_version: "1.0"


Execution
=========

Processor execution will use the following procedure:

The payload is checked to make sure it contains a valid block number, the
previous block id, signer public key, and header_signature are all valid hex,
and that the timestamp is greater than zero. If any of theses checks fail, the
transaction is invalid.

Read the most recent block number, oldest block number, target number of blocks,
and synchronization tolerance from the config zero-address.

If the config does not exist, treat this transaction as the first entry. Add
the sync time and target count to the config object, along with the block_num
from the payload. Add update config and new block info to state.

If the config does exist, do the following checks.

If target_count was set in the transaction, use the new value as the target
number of blocks for the rest of the procedure and update the config.

If sync_tolerance was set in the transaction, use the new value as the
synchronization tolerance for the rest of the procedure and update the config.

Verify the block number in the new BlockInfo message is one greater than the
block number of the most recent block stored in state.  If not, this transactions
is invalid.

Verify the timestamp in the new BlockInfo message follows the rules below.
If it does not, this transaction is invalid.

Verify the previous block id in the new BlockInfo message is equal to the block
id of the most recent block stored in state. If it is not equal, the transaction
is invalid.

Finally, calculate the address for the new block number. Write the new BlockInfo
message to state at the address computed for that block.

If number of blocks stored in state is greater than the target number of
blocks, delete the oldest BlockInfo message from state.

Write the most recent block number, oldest block number, and target number of
blocks to the config zero-address.

Timestamps
----------
Handling timestamps in a distributed network is a difficult task because peers
may not have synchronized clocks. The “clock” of the network may become skewed
over time, either because of peers with substantially different clocks or
bad actors may have an incentive to skew the clock. If the clock of the network
becomes skewed, transactions that depend on the clock may become unexpectedly
invalid. If block validation depends on timestamp validation, peers may not be
able to publish blocks until their clocks are adjusted to better match the
network’s clock.

The BlockInfo Transaction Family will use the following timestamp validation
rules:

  1. The timestamp in the new BlockInfo message must be greater than the
     timestamp in the most recent BlockInfo message in state.
  2. The timestamp in the new BlockInfo message must be less than the peer’s
     measured local time, adjusted to UTC, plus a network time synchronization
     tolerance that is greater than or equal to zero.

Rule 1 enforces monotonicity of timestamps. Rule 2 adds a requirement to the
network that all peers be roughly synchronized. It also allows historic blocks
to be validated correctly.

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
