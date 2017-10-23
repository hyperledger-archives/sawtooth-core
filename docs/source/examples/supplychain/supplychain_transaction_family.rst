*******************************
Supply Chain Transaction Family
*******************************

Overview
=========

The Supply Chain Transaction Processor (SCTP) provides a mechanism for
storing records of asset ownership. The SCTP tracks records, which correlate
to a real world item. Every Record has an owner and a custodian, which can
be the same Agent. The owner is the Agent the legally owns the good. The
custodian is the Agent that is in possession of the good, which may be a
warehousing service, transportation service, etc. Agents are actors in the
system that can manipulate the Records by updating them or transferring
their role to other Agents. Agents are identified by their public key and
authenticated by the signature on the transactions they submit. Transfer of
roles (Owner, Custodian) between Agents is done via an Application process,
where the Agent wishing to assume the role applies for the new role and the
Agent in the role currently can either accept or reject that Application.

This is a proof of concept Transaction Processor that is actively being
developed. As such it has not been thoroughly tested and there will potentially
be breaking changes made to it.

State
=====

This section describes in detail how SCTP objects are stored and addressed in
the global state. All objects in state are stored as encoded Protobufs. Each
type of object below is stored in containers at nodes in the Merkle trie. The
address of the Merkle nodes is detailed below in the addressing section. The
entry at the nodes is a container object that allows for multiple items to be
stored at that node if there is an address collision. All items stored in state
include their natural key. When an address collision occurs the items stored at
the address are searched to find the item with the natural key that matches the
key being searched for.

SCTP stores the following data objects:

Agent
-----

Agents represent owners or custodian of goods in the system. All agents must
be registered in the system before they can interact with records.

.. code-block:: protobuf

    message Agent {
        string identifier = 1; // the hex-encoded public key of the Agent
        string name = 2; // a human readable name
    }

    // Container for on-chain Agents.
    // Allows multiple to be saved at a single address in case of hash collision.
    message AgentContainer {
        // List of Agents - more than one implies a state address collision
        repeated Agent entries = 1;
    }

Application
-----------

An Application is an offer from an agent to change the Custodian or Owner field
of a Record. Agents can only have one open application of a type at a time.

.. code-block:: protobuf

    message Application {

        string record_identifier = 1; // the natural key of the record
        string applicant = 2; // public key of the applicant
        int64 creation_time = 3;

        // Whether the application is a request for ownership or custodianship
        enum Type {
            OWNER = 0;
            CUSTODIAN = 1;
        }
        Type type = 4;

        // The current acceptance status of the Application
        enum Status {
            OPEN = 0;
            CANCELED = 1;
            REJECTED = 2;
            ACCEPTED = 3;
        }
        Status status = 5;

        string terms = 6; // the terms of the application. Human readable.
    }

    message ApplicationContainer {
        repeated Application entries = 1;
    }

Record
------
A record represents a good or material that is being tracked in the system.

.. code-block:: protobuf

    message Record {
        string identifier = 1; // the natural key of the record, serial number or
        // attached sensor identifier

        int64 creation_time = 2; // the time the record was created

        message AgentRecord {
            string agent_identifier = 1; // the public key of the agent
            int64 start_time = 2; // the time the agent started in the role
        }
        repeated AgentRecord owners = 3; // list of the owners, ordered from oldest
        // to newest. The first by definition is the creator of the record.
        // The last is the current owner of the record.
        repeated AgentRecord custodians = 4; // ordered list of custodians.
        // Same ordering as the owners list.

        bool final = 5; // is the record finalized, finalized records cannot be
        // changed.
    }

    message RecordContainer {
        repeated Record entries = 1;
    }

Addressing
----------

When a setting is read or changed, it is accessed by addressing it using the
following algorithm:

The SCTP uses these three namespaces to store the corresponding objects:
    - supplychain.agent
    - supplychain.application
    - supplychain.record

The strings are converted to a Merkle prefix by taking the first 6 characters
of the hex encoded SHA-512 hash of the string.

Agent addresses are generated with ``sha512(agent_pub_key)``, and prepended
with the ``supplychain.agent`` namespace.

.. code-block:: python

    address = hashlib.sha512(public_key.encode()).hexdigest()[0:64]


Applications are stored using the Record address and the
``supplychain.application`` namespace. This stores all applications for a
record at the same address. The correct Application must be searched for using
the ``public_key`` of the applicant, the Application type, and the Application
status.

.. code-block:: python

    address_addr = namespace + sha512(record_identifier)).hexdigest()[0:64]

Record addresses are a generated SHA-512 hash of the record's natural key
prepended with the ``supplychain.record`` namespace.

.. code-block:: python

    address = hashlib.sha512(record_identifier.encode()).hexdigest()[0:64]


Transactions
============

Transaction Headers
-------------------

The settings for the common Sawtooth transaction header fields.

.. code-block:: javascript

    {
        family_name: "sawtooth_supplychain"
        family_version: "0.5"
        encoding: "application/protobuf"
    }

Inputs and Outputs
++++++++++++++++++

The inputs for Supply Chain family transactions must include:
- The address of the object the transaction is operating on if it is a Record
operation
- Any Agents involved in the operation

The outputs for Supply Chain family transactions must include:
- The address of the object the transaction is operating on if it is a Record
operation
- Any Agents involved in the operation

Dependencies
++++++++++++

Transactions should be batched and specify any transactions that they expect
to be committed as dependencies.


Transaction Payload
===================

All SCTP transactions are wrapped in a payload object that allows for the items
to be dispatched to the correct handling logic.


.. code-block:: protobuf

    message SupplyChainPayload {
        // Describes the action this payload is initiating.
        // Used to "route" the data to the proper handler.
        enum Action {
            AGENT_CREATE = 0;
            APPLICATION_CREATE = 1;
            APPLICATION_ACCEPT = 2;
            APPLICATION_REJECT = 3;
            APPLICATION_CANCEL = 4;
            RECORD_CREATE = 5;
            RECORD_FINALIZE = 6;
        }

        Action action = 1;

        bytes data = 2;
    }


Agent Transactions
------------------

Create Agent
++++++++++++

Register a signing participant that can update Records and Applications. The
``signer_public_key`` in the transaction header will be used as the Agent's public
key.

.. code-block:: protobuf

    message AgentCreatePayload {
        string name = 1;
    }


Record Operations
-----------------

Create Record
+++++++++++++

Create a record of an item to be tracked. The current Owner and Custodian is
set to the signer of this transaction.

.. code-block:: protobuf

    message RecordCreatePayload {
        string identifier = 1;
        int64 creation_time = 2;
    }

Create Application
++++++++++++++++++

Create a request for transfer of ownership or custodianship of the record.

.. code-block:: protobuf

    message ApplicationCreatePayload {
        string record_identifier = 1;
        int64 creation_time = 2;
        Application.Type type = 3;
        string terms = 4;
    }


Accept Application
++++++++++++++++++

Accept an Application for transfer of ownership or custodianship of a Record.
Must be submitted by the current Owner or Custodian.

.. code-block:: protobuf

    message ApplicationAcceptPayload {
        string record_identifier = 1;
        string applicant = 2;
        Application.Type type = 3;
        int64 timestamp = 4;
    }

Reject Application
++++++++++++++++++

Reject an Application for transfer of ownership or custodianship of the
record. Must be submitted by the current Owner or Custodian depending on
Application type.

.. code-block:: protobuf

    message ApplicationRejectPayload {
        string record_identifier = 1;
        string applicant = 2;
        Application.Type type = 3;
    }

Cancel Application
++++++++++++++++++

Cancel an Application for transfer of ownership or custodianship of the record.
Must be submitted by the applicant.

.. code-block:: protobuf

    message ApplicationCancelPayload {
        string record_identifier = 1;
        string applicant = 2;
        Application.Type type = 3;
    }


Finalize Record
+++++++++++++++

Mark the record as final (no longer able to be updated). The Owner must be
the current Custodian and this transaction must be signed by the Owner.

.. code-block:: protobuf

    message RecordFinalizePayload {
        string identifier = 1;
    }

Execution
=========

Agents can only be created by transactions signed with their private key.

Records exist in an active modifiable state until they are finalized. Once a
Record is finalized, it can be thought of as destroyed. A finalized item
has either been consumed in manufacturing, lost, or the victim of an
unfortunate accident.

Applications can only be created by the applying Agent and then transitioned
to either an Accepted state, which means the proposal has been executed and the
role on the Record has been updated, or a closed state (Rejected/Canceled) if
either of the Agents involved do not want the application.
