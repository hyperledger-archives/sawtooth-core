************************************
Seth Transaction Receipts and Events
************************************

In order to satisfy the JSON RPC calls eth_getTransactionReceipt, eth_getLogs,
and related calls, Seth transactions in Sawtooth provide the following
information through Sawtooth transaction receipts and events:

- Contract address: the EVM address of the contract created during the
  transaction, if any
- Logs: a list of log entries produced during the execution of the transaction
- Gas used: the quantity of gas used during the execution of the transaction

In addition, the execution result from the EVM is included, so that
the result can be returned to the client that submitted the transaction.

The remaining pieces of data required by the JSON-RPC responses are related to
the context of a committed transaction within its respective block.
Consequently, the information can be computed at request time. These pieces are:

- Block hash: the header signature of the block containing the transaction
- Block number: the block’s number
- Transaction hash: the transaction header signature
- Transaction index: the index of the transaction within the block
- Cumulative gas used: the total gas used by all EVM transactions in the block
  preceding and including this transaction

Receipt Data
============

Receipt data for a given transaction is limited to what can be computed during
the execution of a transaction. Given that a transaction processor’s knowledge
is limited to that of the transaction itself and current state, the values that
may be included in an individual receipt are limited.

Receipt data from an individual transaction is comprised of the following
protobuf message. The serialized message is wrapped in a TransactionReceipt.Data
message, as specified in "Events and Transaction Receipts". The receipt
data_type field is set to “seth_receipt”:

.. code-block:: protobuf

  message EvmTransactionReceipt {
      bytes contract_address = 1; // A contract address, if created
      uint64 gas_used = 2; // The gas consumed by this transaction
      bytes return_value = 3; // The return value of the contract execution
  }

Log Events
==========

Ethereum defines a set of LOGX instructions that allow contracts to log
off-chain data. Solidity uses these instructions to implement an event
subscription system. To make Seth compatible with both, the LOGX instructions
generate Sawtooth events. These events contain only the data that is available
during transaction execution.

The log events are wrapped in a TransactionEvent, as specified in :doc:`Events
and Transactions Receipts<../architecture/events_and_transactions_receipts>`.
The event_type field is set to “seth_log_event”. The event_data from an
individual transaction contains the following protobuf message.

.. code-block:: protobuf

  // Example Sawtooth event capturing EVM logs
  Event {
  	event_type = "seth_log_event",
  	event_data = <serialized EvmLogData>,
    attributes = [
      Attribute { "address": <evm address as hex> },
  	],
  }

  // Protobuf message to store in the Sawtooth Event's event_data field
  message EvmLogData {
      // 20 Bytes - address from which this log originated.
      bytes address = 1;

      // Array of 0 to 4 32-byte blobs of data.
      // (In solidity: The first topic is the hash of the signature
      // of the event (e.g. Deposit(address,bytes32,uint256)), except
      // you declared the event with the 'anonymous' specifier.)
      // See the following:
      // https://github.com/ethereum/wiki/wiki/JSON-RPC#eth_getfilterchanges
      repeated bytes topics = 2;

      // contains one or more 32 Bytes non-indexed arguments of the log.
      bytes data = 3;
  }

The address in this entry refers to the contract address that created the
message. The data is an opaque set of bytes, set by the contract.
