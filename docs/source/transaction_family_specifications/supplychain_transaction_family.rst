***************************************
Supply Chain Transaction Family
***************************************

Overview
=========

The Supplychain Transaction Processor(SCTP) provides a mechanism for
storing records of asset location and ownership.

State
=====

This section describes in detail how SCTP objects are stored and addressed in the global state.

SCTP stores the following data objects:

Agent
-----

Agents represent owners or holders of goods in the system. All agents must be registered in the system before they can be used.

.. code-block:: javascript

    {
        Name: "name", // The name of the agent
        Type: "type", // Agent type, domain specific value
        Url: // The web address of the agent as a fully qualified URL
        OwnRecords: [], // list of all records(by address) this agent owns
        HoldRecords: [], // list of all records(by address) this agent holds
        OpenApplications: [], // list of all applications(by records address) this agent owns
        AcceptedApplications: [] // list of all records this agent owns
    }

For "HoldRecords", a value 1 indicates there is an open application against the record, 0 means no open application.

For "OwnRecords" the value 1 means Held and Owned, 0 means Owned and not held.

For "OpenApplications" indicates the agent has an application open against a record and is waiting for a response.

For "AcceptedApplications" indicates the agent has an application accepted against a record and can now create a child. The value is the sensor ID associated with the record.


Record
------
A record represents a good or material that is being tracked in the system.

.. code-block:: javascript

    {
        RecordInfo: {
            Owner: agent_address,  // the owner of the item
            Custodians: [],  // A list of custodians(identified by address) for the record.
            CurrentHolder: agent_address,  // The agent in possession of the item, either the Owner or the current Custodian
            Timestamp: timestamp,  // time stamp of record creation, seconds from the epoc
            Sensor: 'sensor_id',  // identifier of sensor attached to item
            Final: true | false,  // once set true the record cannot be updated
            ApplicationFrom: agent_address,  //  The address of the applicant
            ApplicationType: "Owner" | "Custodian",  // Which field is the application for.
            ApplicationTerms: "text",  // human readable terms of the transfer application.
            ApplicationStatus:  "Open" | "Rejected" | "Cancelled"
        }
    }


Addressing
----------

When a setting is read or changed, it is accessed by addressing it using the following algorithm:

The SCTP uses the Supplychain namespace computed as the first 6 hex characters of:
.. code-block:: javascript

    namespace = sha512('Supplychain')).hexdigest()[:6]

Agent addresses are generated sha512(agent_pub_key), prepended with the Supplychain namespace.

.. code-block:: javascript

    agent_addr = namespace + sha512(agent_pub_key)).hexdigest()

Record addresses are generated sha512 of the initial record data, prepended with the Supplychain namespace.

.. code-block:: javascript

    record_addr = namespace.sha512(initial_record_data)).hexdigest()


Transactions
============

Transaction Headers
-------------------

The settings for the common Sawtooth Transaction header fields.

.. code-block:: javascript

    {
        family_name: "sawtooth_supplychain"
        family_version: "0.5"
        encoding: "application/json"
    }

Inputs and Outputs
++++++++++++++++++
The inputs for config family transactions must include:
the address of the object the transaction is operating on
if it is a record operation it must contain any agents involved in the operation.
The outputs for config family transactions must include:
the address of the object the transaction is operating on
if it is a record operation it must contain any agents involved in the operation.

Dependencies
++++++++++++
    None


Transaction Payload
===================

All SCTP transactions take a minimum the following fields.

.. code-block:: javascript

    {
        MessageType: "Agent" | "Record", // What data is this transaction operating on
        Action: "action", // Operation to perform, value depend on MessageType. See Transactions below for possible values.
    }


Agent Transactions
------------------

Create Agent
++++++++++++

Create an agent record, agent address will be calculated from the public key
extracted from the transactions signature.

.. code-block:: javascript

    {
        MessageType: 'Agent',
        Action: 'Create',
        // Create Agent fields
        Name: 'name',  // Name of the agent to create
        Type: 'type',  // Domain relevant type
        Url: 'url',  // Link for more information
    }

Record Operations
-----------------

Create Record
+++++++++++++

Create a record of an item to be tracked. The current Owner and Custodian is
set to the signer of this transaction.

.. code-block:: javascript

    {
        MessageType: 'Record',
        Action: 'Create',
        // Create Record fields
        RecordId: record_addr, // address
        Timestamp: timestamp // current time, seconds from the epoch
    }

Create Application
++++++++++++++++++

Create an application for transfer of ownership or custodianship of the record.

.. code-block:: javascript

    {
        MessageType: 'Record',
        Action: 'CreateApplication',
        // Create Application fields
        RecordId: record_address,
        ApplicationType: "Owner" | "Custodian",
        ApplicationTerms: 'terms', // human readable terms of the transfer.
    }

Accept Application
++++++++++++++++++

Accept an application for transfer of ownership or custodianship of the record. Must be submitted by the current owner or custodian.

.. code-block:: javascript

    {
        MessageType: 'Record',
        Action: 'AcceptApplication',
        // Accept Application fields
        RecordId: record_address
    }

Reject Application
++++++++++++++++++

Reject an application for transfer of ownership or custodianship of the record. Must be submitted by the current owner or custodian.

.. code-block:: javascript

    {
        MessageType: 'Record',
        Action: 'RejectApplication',
        // Reject Application Fields
        RecordId: record_address,
    }

Cancel Application
++++++++++++++++++

Cancel an application for transfer of ownership or custodianship of the record. Must be submitted by the Applicant.

.. code-block:: javascript

    {
        MessageType: 'Record',
        Action: 'CancelApplication',
        // Cancel Application Fields
        RecordId: record_address,
    }

Finalize Record
+++++++++++++++

Mark the record as final (no longer able to be updated). The owner must be
the current custodian and this transaction must be signed by the owner.

.. code-block:: javascript

    {
        MessageType: 'Record',
        Action: 'Finalize',
        // Finalize Record Fields
        RecordId: record_address
    }

Execution
=========

The current implementation simple and does not have many validity checks in
place to enforce data integrity. For example maximum string lengths are not
enforce on Agent information fields (Type and Url).

The transaction processor does enforce implied 'foreign key'
relationships between objects. The Agent fields OwnRecords, HoldRecords, OpenApplications, and AcceptedApplications are validated against the
corresponding Record fields. The Agent fields are present to allow
clients to provide quick access to Agent information for reporting purposes.

