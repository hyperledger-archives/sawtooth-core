**********************
Transaction Scheduling
**********************

Sawtooth supports both serial and parallel scheduling of transactions. The
scheduler type is specified via a command line argument or as an option in the
validator's configuration file when the validator process is started.  Both
schedulers result in the same deterministic results and are completely
interchangeable.

The parallel processing of transactions provides a performance improvement for
even fast transaction workloads by reducing overall latency effects which occur
when transaction execution is performed serially.  When transactions are of
non-uniform duration (such as may happen with more realistic complex
workloads), the performance benefit is especially magnified when faster
transactions outnumber slower transactions.

Transaction scheduling and execution in Sawtooth correctly and efficiently
handles transactions which modify the same state addresses, including
transactions within the same block.  Even at the batch level, transactions can
modify the same state addresses. Naive distributed ledger implementations may
not allow overlapping state modifications within a block, severely limiting
performance of such transactions to one-transaction-per-block, but Sawtooth has
no such block-level restriction. Instead, state is incremental per transaction
execution. This prevents double spends while allowing multiple transactions
which alter the same state values to appear in a single block. Of course, in
cases where these types of block-level restrictions are desired, transaction
families may implement the appropriate business logic.

Scheduling within the Validator
===============================

The validator has two major components that use schedulers to
calculate state changes and the resulting Merkle hashes based on transaction
processing: the :ref:`Chain Controller <journal-chain-controller-label>`
and the :ref:`Block Publisher <journal-block-publisher-label>`.
These two components pass a scheduler to the Executor. While the validator
contains only a single Chain Controller, a single Block Publisher, and a single
Executor, there are numerous instances of schedulers that are dynamically
created as needed.

Chain Controller
----------------

The Chain Controller is responsible for maintaining the current chain head (a
pointer to the last block in the current chain).  Processing is block-based;
when it receives a candidate block (over the network or from the Block
Publisher), it determines whether the chain head should be updated to point to
that candidate block.  The Chain Controller creates a scheduler to calculate
new state with a related Merkle hash for the block being published. The Merkle
hash is compared to the state root contained in the block header. If they
match, the block is valid from a transaction execution and state standpoint.
The Chain Controller uses this information in combination with consensus
information to determine whether to update the current chain head.

Block Publisher
---------------

The Block Publisher is responsible for creating new candidate blocks.  As
batches are received by the validator (from clients or other validator nodes),
they are added to the Block Publisher's pending queue.  Only valid transactions
will be added to the next candidate block.  For timeliness, batches are added
to a scheduler as they are added to the pending queue; thus, transactions are
processed incrementally as they are received.

When the pending queue changes significantly, such as when the chain head has
been updated by the Chain Controller, the Block Publisher cancels the current
scheduler and creates a new scheduler.

.. _txn-sched-executor-label:

Executor
--------

The Executor is responsible for the execution of transactions by sending them
to transaction processors.  The overall flow for each transaction is:

1. The Executor obtains the next transaction and initial context from the
   scheduler.
#. The Executor obtains a new context for the transaction from the Context
   Manager by providing the initial context (contexts are chained together).
#. The Executor sends the transaction and a context reference to the transaction
   processor.
#. The transaction processor updates the context's state via context manager
   calls.
#. The transaction processor notifies the Executor that the transaction is
   complete.
#. The Executor updates the scheduler with the transaction's result with the
   updated context.

In the case of serial scheduling, step 1 simply blocks until the previous
transaction's step 6 has completed.  For the parallel scheduler, step 1
blocks until a transaction exists which can be executed because its
dependencies have been satisfied, with steps 2 through 6 happening in
parallel for each transaction being executed.

.. _arch-iterative-sched-label:

Iterative Scheduling
====================

Each time the executor requests the next transaction, the scheduler calculates
the next transaction dynamically based on knowledge of the transaction
dependency graph and previously executed transactions within this schedule.

Serial Scheduler
----------------

For the serial scheduler, the dependency graph is straightforward; each
transaction is dependent on the one before it.  The next transaction is
released only when the scheduler has received the execution results from the
transaction before it.

Parallel Scheduler
------------------

As batches are added to the parallel scheduler, predecessor transactions are
calculated for each transaction in the batch.  A predecessor transaction is
a transaction which must be fully executed prior to executing the transaction
for which it is a predecessor.

Each transaction has a list of inputs and outputs; these are address
declarations fields in the transaction's header and are filled in by the client
when the transaction is created. Inputs and outputs specify which locations in
state are accessed or modified by the transaction. Predecessor transactions are
determined using these inputs/outputs declarations.

.. note::

   It is possible for poorly written clients to impact parallelism by providing
   overly broad inputs/outputs declarations.  Transaction processor
   implementations can enforce specific inputs/outputs requirements to
   provide an incentive for correct client behavior.

The parallel scheduler calculates predecessors using a Merkle-Radix tree with nodes
addressable by state addresses or namespaces. This tree is called the
predecessor tree. Input declarations are considered reads, with output
declarations considered writes.  By keeping track of readers and writers within
nodes of the tree, predecessors for a transaction can be quickly determined.

Unlike the serial scheduler, the order in which transactions will be returned
to the Executor is not predetermined.  The parallel scheduler is careful about
which transactions are returned; only transactions with do not have state
conflicts will be executed in parallel. When the Executor asks for the next
transaction, the scheduler inspects the list of unscheduled transactions; the
first in the list for which all predecessors have finished executed will be be
returned.  If none are found, the scheduler will block and re-check after
a transaction has finished being executed.

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
