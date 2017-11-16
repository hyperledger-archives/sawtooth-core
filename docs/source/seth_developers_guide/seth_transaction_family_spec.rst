..
   Copyright 2017 Intel Corporation

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.

*************************************
Seth Transaction Family Specification
*************************************

Overview
=========
The Seth transaction family enables the creation and execution
of smart contracts within the Hyperledger Sawtooth framework. It integrates the
Hyperledger Burrow implementation of the Ethereum Virtual Machine (EVM) into
the Hyperledger Sawtooth framework using the Sawtooth Transaction Processor SDK.

The primary problems to solve in order to integrate the Burrow EVM into
Sawtooth are:

1. Define and implement an efficient mapping between EVM World State addresses
   and Sawtooth Global State addresses.
2. Define and implement an efficient method for maintaining accounts and
   account storage in Sawtooth Global State.
3. Define and implement an “EVM-Wrapper” at the Transaction Processor level for
   handling additional “Ethereum-like” and “Burrow-like” features not
   implemented by the EVM, including:

    a. Handling account creation transactions and storing the resulting code in
       global state.
    b. Managing and enforcing account permissions.
    c. Maintaining account balances and transferring funds between accounts.
    d. Checking transaction nonces against account nonces and deriving new
       contract account addresses.

4. Define and implement an efficient API for:

    a. Submitting transactions to the network that load and execute EVM byte
       code in a way that is compatible with existing tools.
    b. Querying state using smart contracts without requiring that state be
       modified.

5. Define and implement an event subscription system for monitoring the EVM
   namespace that can be used with solidity events.

This spec assumes a basic knowledge of Ethereum, Hyperledger Burrow, and
Hyperledger Sawtooth.

For more information on Ethereum and the EVM, see the `Ethereum Yellow Paper`_.

.. _Ethereum Yellow Paper: https://ethereum.github.io/yellowpaper/paper.pdf

For more information on `Hyperledger Burrow`_, check out the project.

.. _Hyperledger Burrow: https://github.com/hyperledger/burrow

State
=====

Accounts
--------
State associated with the Seth Transaction Family shall consist
of a set of accounts. Similar to Ethereum, two types of accounts shall be
defined:

* Externally Owned Accounts (EOAs)
* Contract Accounts (CAs)

EOAs are accounts that are owned by an external actor (ultimately a person).
They are created implicitly whenever a private key is generated but an account
creation transaction must be submitted to initialize the contract in global
state.

CAs are created and owned by other accounts (either an EOA or another CA). All
CAs are ultimately associated with an EOA.

For more information on Ethereum Accounts, see the `Ethereum Documentation`_.

.. _Ethereum Documentation: http://ethdocs.org/en/latest/account-management.html#accounts

Account Storage Format
----------------------
Accounts and any associated account storage shall be stored in global state
using the following protobuf message format:

.. code-block:: protobuf

    message EvmEntry {
        EvmStateAccount account = 1;
        repeated EvmStorage storage = 2;
    }

    message EvmStateAccount {
        bytes address = 1;
        int64 balance = 2;
        bytes code = 3;
        int64 nonce = 4;
        EvmPermissions permissions = 5;
    }

    message EvmPermissions {
      // Bit array where true means "has permission" and false means "doesn't have
      // permission"
      uint64 perms = 1;

      // Bit array where true means "the permission has been set" and false means
      // "the permission has not been set".
      uint64 set_bit = 2;
     }

    message EvmStorage {
        bytes key = 1;
        bytes value = 2;
    }

The following fields defined above shall be ignored for this version of the
spec:

* balance - Since this version of the spec does not include an incentive system
  or associated cryptocurrency, maintaining a balance isn’t meaningful.

Addressing
==========

EVM Prefix
----------
All data associated with the Seth Transaction Family shall be
stored under the prefix formed by taking the first 3 bytes of the SHA512 hash
of the UTF-8 encoded string “seth”. This shall be referred to as the EVM
prefix.::

    >>> hashlib.sha512('seth'.encode('utf-8')).hexdigest()[0:6]
    'a68b06'

Account Addresses
-----------------
The address of an account depends on which type of account it is:

* EOA - Given an EOA’s private key, the address is the, “rightmost 160-bits of
  the Keccak hash of the corresponding ECDSA public key,” from the yellow paper.
  The “Keccak hash” shall be taken to mean SHA3.
* CA - The address of a CA is the last 20 bytes of the 256-byte SHA3 hash of
  the byte array formed by concatenating the sender address and the big endian
  encoding of the sender’s current nonce. In other words, the address of a CA is
  derived from hashing the creating accounts address and its nonce.

Accounts in the above format shall be stored in global state at the address
formed by concatenating the EVM prefix, address of the account, and enough 0’s
to form a valid global state address.::

    >>> state_address = 'a84eda' + account_address + '0'*12

Transaction Payload
===================

In the Seth Transaction Family, the transaction payload shall be represented
using the following protobuf message:

.. code-block:: protobuf

    message SethTransaction {
      enum TransactionType {
        DEFAULT = 0;
        CREATE_EXTERNAL_ACCOUNT = 1;
        CREATE_CONTRACT_ACCOUNT = 2;
        MESSAGE_CALL = 3;
        SET_PERMISSIONS = 4;
      }

      TransactionType transaction_type = 1;

      // To eliminate the need for two deserialization steps, all types of
      // transactions are included as fields, but only the field indicated by the
      // transaction type should be set.
      CreateExternalAccountTxn create_external_account = 2;
      CreateContractAccountTxn create_contract_account = 3;
      MessageCallTxn message_call = 4;
      SetPermissionsTxn set_permissions = 5;
    }

The following are the representation of the different transaction types that
can be included in the above SethTransaction:

.. code-block:: protobuf

    // The following transactions have fields that correspond to the transaction
    // structure defined at: https://ethereum.github.io/yellowpaper/paper.pdf
    // Quoted descriptions are from this paper.

    message CreateExternalAccountTxn {
      // "...the number of transactions sent by the sender; formally T_n."
      uint64 nonce = 1;

      // "...the 160-bit address of the message call's recipient or, for a
      // contract creation transaction, {}, used here to denote (the empty byte
      // array); formally T_t."
      bytes to = 2;

      // The Burrow-EVM permissions to assign to the new account
      EvmPermissions permissions = 3;
    }

    message CreateContractAccountTxn {
      // "...the number of transactions sent by the sender; formally T_n."
      uint64 nonce = 1;

      // "...the number of Wei to be paid per unit of gas for all computation
      // costs incurred as a result of the execution of this transaction;
      // formally T_p."
      uint64 gas_price = 2;

      // "...the maximum amount of gas that should be used in executing this
      // transaction. This is paid up-front, before any computation is done and
      // may not be increased later; formally T_g"
      uint64 gas_limit = 3;

      // "...the number of Wei to be transferred to the message call's recipient
      // or, in the case of contract creation, as an endowment to the newly
      // created account; formally T_v."
      uint64 value = 4;

      // "An unlimited size byte array specifying the EVM-code for the account
      // initialisation procedure, formally T_i."
      //
      // This should only be set if this is a contract creation transaction.
      bytes init = 5;

      // The Burrow-EVM permissions to assign to this account
      EvmPermissions permissions = 6;
    }

    message MessageCallTxn {
      // "...the number of transactions sent by the sender; formally T_n."
      uint64 nonce = 1;

      // "...the number of Wei to be paid per unit of gas for all computation
      // costs incurred as a result of the execution of this transaction;
      // formally T_p."
      uint64 gas_price = 2;

      // "...the maximum amount of gas that should be used in executing this
      // transaction. This is paid up-front, before any computation is done and
      // may not be increased later; formally T_g"
      uint64 gas_limit = 3;

      // "...the 160-bit address of the message call's recipient or, for a
      // contract creation transaction, {}, used here to denote (the empty byte
      // array); formally T_t."
      bytes to = 4;

      // "...the number of Wei to be transferred to the message call's recipient
      // or, in the case of contract creation, as an endowment to the newly
      // created account; formally T_v."
      uint64 value = 5;

      // "An unlimited size byte array specifying the input data of the message
      // call, formally T_d."
      //
      // This should only be set if this is a message call transaction.
      bytes data = 6;
    }

    message SetPermissionsTxn {
      // "...the number of transactions sent by the sender; formally T_n."
      uint64 nonce = 1;

      // "...the 160-bit address of the message call's recipient or, for a
      // contract creation transaction, {}, used here to denote (the empty byte
      // array); formally T_t."
      bytes to = 2;

      // The Burrow-EVM permissions to assign to this account
      EvmPermissions permissions = 3;
    }

The following fields defined above shall be ignored for this version of the
spec, but will be used in later versions:

* gas_price - Since this version of the spec does not include an incentive
  system or account balances, a gas_price is not meaningful since there is
  nothing to purchase gas with. Instead, the client supplied gas_limit will
  serve to limit the amount of gas used by a given transaction.
* value - Since this version of the spec does not include an incentive system
  or account balances, transferring value between accounts is not meaningful.

Execution
=========

Transaction execution shall follow a simplified version of the Ethereum model
described below:

1. The payload will be unpacked and validated. If the payload is missing or the
   payload is malformed in any way, the transaction is invalid.
2. The header of the transaction is checked. If the header is malformed or does
   not have a public key, the transaction is invalid.
3. The sender address shall be calculated by taking the rightmost 160 bits of
   the SHA3 hash of the public key used to submit the transaction. This public
   key is included in the transaction header. If the public key cannot be
   decoded or the sender cannot be determined from the public key, the
   transaction is invalid.
4. If the transaction type is MESSAGE_CALL,

    a. The sender’s account will be retrieved from state using the sender
       address. If the account does not exist, the transaction is invalid.
    b. Check that the account has permissions to make message calls. If the
       account does not have permissions, the transaction is invalid.
    c. Check that the nonce in the transaction matches the nonce stored in state
       for the account. If it does not, the transaction is invalid.
    d. The receiver’s account will be retrieved from state using the address in
       the `to` field. If the address is invalid, the account does not exist, or
       the account does not contain any code, the transaction is invalid.
    e. The EVM will be called using:

        - The sender account for the `caller` argument
        - The receiver account for the `callee` argument
        - The `code` field in the receiver’s account for the `code` argument
        - The `data` field in the transaction payload for the `input` argument.
          If no data field is set, the transaction is invalid.
        - 0 for the `value` argument.
        - The `gas_limit` field in the transaction payload for the `gas`
          argument.

    f. The resulting output from the EVM shall be stored in a
       SethTransactionReceipt.
    g. The sender nonce is incremented.
    h. The sender and receiver accounts and associated storage shall be pushed
       to state.

5. If the transaction is CREATE_CONTRACT_ACCOUNT,

    a. The sender’s account will be retrieved from state using the sender
       address. If the account does not exist, the transaction is invalid.
    b. Check that the account has permissions to make contract accounts. If the
       account does not have permissions, the transaction is invalid.
    c. Check that the nonce in the transaction matches the nonce stored in state
       for the account. If it does not, the transaction is invalid.
    d. A Contract Account shall be created at a new address derived from the
       sender account as described above. The sender account’s nonce shall then
       be incremented.
    e. Validate that that creating account has permissions to set permissions
       if permissions are included. If it does not have permission the
       transaction is invalid.
    f. If the `init` field is set in the transaction payload, the EVM will be
       called using:

        - The sender account for the `caller` and `callee` arguments
        - The `init` field for the `code` argument
        - `nil` for the `input` argument.
        - 0 for the `value` argument.
        - The `gas_limit` field in the transaction payload for the `gas`
          argument.

    g. The resulting output from the EVM shall be stored in the `code` field of
       the newly created account and shall be stored in a
       SethTransactionReceipt.
    h. The sender account, newly created account, and permissions shall be
       pushed to state.

6. If the transaction is CREATE_EXTERNAL_ACCOUNT and the sender is new,

    a. A External Account address shall be created. If an account already
       exists at that address, the transaction is invalid.
    b. Check global permissions to see if the account can be created. If the
       account cannot be created, the transaction is invalid. New accounts
       inherit global permissions. If global permissions are not set, give
       account all permissions.
    c. The resulting output shall be stored in the `code` field of
       the newly created account and shall be stored in a
       SethTransactionReceipt.
    d. The sender account, newly created account, and any permissions shall be
       pushed to state.

7. If the transaction is CREATE_EXTERNAL_ACCOUNT and the sender exists,

    a. If the sender exists and wants to make more accounts, check that the
       creating account has permissions to make accounts. If the account does
       not have permissions, the transaction is invalid.
    b. Check that the nonce in the transaction matches the nonce stored in
       state for the account. If it does not, the transaction is invalid.
    c. A External Account address shall be created. If an account already
       exists at that address, the transaction is invalid.
    d. Validate that that creating account has permissions to set permissions
       if permissions are included. If it does not have permission the
       transaction is invalid.
    e. The resulting output shall be stored in the `code` field of
       the newly created account and shall be stored in a
       SethTransactionReceipt.
    f. The sender nonce is incremented.
    g. The sender account, newly created account, and any permissions shall be
       pushed to state.

8. If the transaction is SET_PERMISSIONS,

     a. Check that permissions are set in the transaction. If there are not
        any permissions, the transaction is invalid.
     b. The sender’s account will be retrieved from state using the sender
        address. If the account does not exist, the transaction is invalid.
     c. Check that the account has permissions to make contract accounts. If the
        account does not have permissions, the transaction is invalid.
     d. Check that the nonce in the transaction matches the nonce stored in state
        for the account. If it does not, the transaction is invalid.
     e. Construct the address for the receiver for the permission change. If the
        the address cannot be constructed, the transaction is invalid.
     f. If the receiver does not exist, the transaction is invalid.
     g. The sender nonce is incremented.
     h. The sender account, receiver account permissions shall be
        pushed to state.


9. If an error occurs while the EVM is executing, the transaction is invalid.

Receipts
========

Seth transaction receipts contain the following serialized protobuf message in
the opaque data field.

.. code-block:: protobuf

  message EvmTransactionReceipt {
      bytes contract_address = 1; // A contract address, if created
      uint64 gas_used = 2; // The gas consumed by this transaction
      bytes return_value = 3; // The return value of the contract execution
  }

The fields of this message are:

- ``contract_address``: If a contract was created during execution of the
  transaction, the EVM address of the contract created. Otherwise, nil.
- ``gas_used``: The quantity of gas used during the execution of the
  transaction.
- ``return_value``: The bytes returned by the EVM after executing the contract
  call or contract initialization data. Otherwise, nil.

The Ethereum specification defines a transaction receipt with additional fields.
However, within Sawtooth, receipt data for a given transaction is limited to
what can be computed during the execution of a transaction. Given that a
transaction processor’s knowledge is limited to that of the transaction itself
and current state, the values that can be included in the Seth receipt are
limited to the above. Additional contextual information that may be required can
be computed later by inspecting the block that the transaction was executed in.

Events
------

Ethereum defines a set of LOGX for X in [0, 4] instructions that allow contracts
to log off-chain data. Solidity uses these instructions to implement an event
subscription system. To make Seth compatible with both, the LOGX instructions
generate :doc:`Sawtooth Events
</architecture/events_and_transactions_receipts>`. Like Seth's transaction
receipts, these events contain only the data that is available during
transaction execution.

The ``event_type`` field is set to ``“seth/log”``. The ``event_data``
field contains a copy of the data argument passed to the EVM LOGX instruction.
an individual transaction contains the following protobuf message. The
``attributes`` field contains:

- An attribute with the key ``"address"`` and the address of the contract that
  generated the event as its value.
- For each topic Y in [1..X], and attribute with the key ``"topicY"`` and the
  topic data for that topic as its value.

.. code-block:: protobuf

  Event {
    event_type = "seth/log",
    event_data = <data passed to LOGX>,
    attributes = [
      Attribute { "address": <contract address> },
      Attribute { "topicX": <topic data> },
  	],
  }
