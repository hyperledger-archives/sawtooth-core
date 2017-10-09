********
Seth-RPC
********

In order to make the Seth Transaction Family useful to existing Solidity
developers, a layer in the Ethereum application stack needs to be identified
where Sawtooth can be positioned. The JSON-RPC interface provided by all
existing Ethereum clients, including the Go Ethereum client geth, has been
identified as the best layer to make the change. It is the interface over which
tools and libraries used by Solidity developers and front-end Javascript
developers interact with an Ethereum network. The most popular tool using this
interface is the Ethereum JavaScript API. It will be used to test that the
interface is functioning correctly.

The seth-rpc server will provide this JSON-RPC interface for connecting
Ethereum JavaScript API to a Sawtooth validator and the Seth Transaction Family.

.. image:: ../images/seth_JSON_RPC.*
   :width: 80%
   :align: center
   :alt: Seth JSON RPC Diagram

In order to keep the seth-rpc server focused and optimized as an adapter, it
exists as a separate process from the existing seth client. However, the
seth-rpc server and the seth client share configuration and key storage to
simplify interactions between the two.

CLI Design
==========

The seth-rpc server shall support the following command line interface:

Usage: seth-rpc [options]

--connect <validator-url>  Connect to the validator at the given URL.

--bind <endpoint>...       Bind to the following addresses and accept JSON-RPC
                           requests on it.

RPC Calls
=========

The following RPC calls will be partially supported.

Transaction Calls
-----------------

- eth_getTransactionCount
- eth_getBlockTransactionCountByHash
- eth_getBlockTransactionCountByNumber
- eth_sendTransaction
- eth_sendRawTransaction
- eth_getTransactionByHash
- eth_getTransactionByBlockHashAndIndex
- eth_getTransactionByBlockNumberAndIndex
- eth_getTransactionReceipt
- eth_gasPrice
- eth_estimateGas

Account Calls
-------------

- eth_getBalance
- eth_getStorageAt
- eth_getCode
- eth_sign
- eth_call
- eth_accounts

Block Calls
-----------

- eth_blockNumber
- eth_getBlockByHash
- eth_getBlockByNumber

Network Calls
-------------

- net_version
- net_peerCount
- net_listening

Log Calls
---------

- eth_newFilter
- eth_newBlockFilter
- eth_newPendingTransactionFilter
- eth_uninstallFilter
- eth_getFilterChanges
- eth_getFilterLogs
- eth_getLogs
