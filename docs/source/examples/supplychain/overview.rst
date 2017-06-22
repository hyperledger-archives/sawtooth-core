*******************
SupplyChain Example
*******************

This example provides the infrastructure necessary to track physical objects in
a real-world supply chain on the Sawtooth Ledger. Records are tracked on the
Ledger, and are uniquely linked to the physical objects they represent.


SupplyChain Overview
=====================

Agents
++++++

Agents represent actors in the system. An Agent is expected most commonly to
represent a company. Agents are identified by their public keys and any
transactions an agent submits must be signed by the agent. Agents serve two
roles in the system: owners and custodians. Owners are Agents that are the
legal holders of the physical object a record represents. Custodians are Agents
that have possesion of the physical object that a Record represents. Custodians
may be transportation, logistics, warehousing companies, or any other company
that has entered into an agreement to care for the item.

The ledger representation of "Agents" is:

.. literalinclude:: ../../../../families/supplychain/protos/agent.proto
    :language: protobuf
    :lines: 22-

Records
+++++++

Records represent physical objects in the world. Records are identified in the
system by `natural keys <https://en.wikipedia.org/wiki/Natural_key>`_. These
natural keys could be the serial number of the object, the RFID tag number,
etc.

Records keep a list of all the Owners and Custodians that have possessed the
item: these records are stored in chronological order from oldest to most
recent. The most recent is the current Agent in that role.

Records may also be finalized. When a record is finalized it means the physical
item has been consumed or destroyed and there can be no more updates to the
Record.

The ledger representation of "Records" is:

.. literalinclude:: ../../../../families/supplychain/protos/record.proto
    :language: protobuf
    :lines: 22-


Applications
++++++++++++

Applications are the mechanism that Agents use to change roles (Owner or
Custodian). Agents that wish to assume a new role for a Record create a new
application that specifies the desired role. The current Agent in that role
must then accept the Application before the  Record is updated. This allows
both Agents to assert their agreement to the change before the update is made.
The applicant(proposing Agent) may cancel the Application or the current Agent
may reject the Application if it is not wanted.

The ledger representation of "Applications" is:

.. literalinclude:: ../../../../families/supplychain/protos/application.proto
    :language: protobuf
    :lines: 22-



SupplyChain Transaction Family
=================================

The SupplyChain Transaction Family is implemented by a Transaction Processor
that manages ledger(global state) representation and integrity.

.. toctree::
   :maxdepth: 2

   supplychain_transaction_family.rst


SupplyChain REST API
====================

The SupplyChain REST API implements a domain specific api for clients to
query SupplyChain Ledger state.

.. toctree::
   :maxdepth: 2

   rest_api/endpoint_specs.rst
   rest_api/error_codes.rst