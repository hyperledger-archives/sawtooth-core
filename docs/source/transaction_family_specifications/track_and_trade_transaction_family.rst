************************************************
Track and Trade Transaction Family Specification
************************************************

Overview
========

The Track and Trade (T&T) transaction family allows users to track
goods as they move through a supply chain. Records for goods include a
history of ownership and custodianship, as well as histories for a
variety of properties such as temperature and location. These
properties are managed through a user-specifiable system of record
types.


State
=====

All T&T objects are serialized using Protocol Buffers before being
stored in state. These objects include: Agents, Properties
(accompanied by their auxiliary PropertyPage objects), Proposals,
Records, and RecordTypes. As described in the Addressing_ section
below, these objects are stored in separate sub-namespaces under the
T&T namespace. To handle hash collisions, all objects are stored in
lists within protobuf "Container" objects.


Records
-------

Records represent the goods being tracked by Track and Trade. Almost
every transaction references some Record.

A Record contains a unique identifier, the name of a RecordType, and
lists containing the history of its owners and custodians. It also
contains a ``final`` flag indicating whether further updates can be
made to the Record and its Properties. If this flag is set to true,
then no further updates can be made to the Record, including changing
its ``final`` flag.

.. code-block:: protobuf

   message Record {
       message AssociatedAgent {
           // The Agent's public key
           string agent_id = 1;

           // Approximately when this agent was associated, as a Unix UTC timestamp
           uint64 timestamp = 2;
       }

       // The unique user-defined natural key which identifies the
       // object in the real world (for example, a serial number)
       string identifier = 1;

       string record_type = 2;

       // Ordered oldest to newest by timestamp
       repeated AssociatedAgent owners = 3;
       repeated AssociatedAgent custodians = 4;

       // Flag indicating whether the Record can be updated. If it is set
       // to true, then the record has been finalized and no further
       // changes can be made to it or its Properties.
       bool final = 5;
   }


Note that while information about a Record's owners and custodians are
included in the object, information about its Properties are stored
separately (see the Properties_ section below).

Records whose addresses collide are stored in a list alphabetically by
identifier.

.. code-block:: protobuf

   message RecordContainer {
       repeated Record entries = 1;
   }

.. _Properties:

Properties
----------

Historical data pertaining to a particular data field of a tracked
object are stored as Properties, represented as a list of values
accompanied by a timestamp and a reporter identifier.

The whole history of updates to Record data is stored in current state
because this allows for more flexibility in writing transaction rules.
For example, in a fish track-and-trade system, there might be a rule
that no fish can be exchanged whose temperature has gone above 40
degrees. This means, however, that it would be impractical to store
all of a Record's data at one address, since adding a single update
would require reading the entire history of each of the Record's
Properties out of state, adding the update, then writing it all back.

To solve this problem, Properties are stored in their own namespace
derived from their name and associated Record. Since some Properties
may have thousands of updates, four characters are reserved at the end
of that namespace in order to paginate a Property's history. The
Property itself (along with name, Record identifier, authorized
reporters, and paging information) is stored at the namespace ending
in ``0000``. The namespaces ending in ``0001`` to ``ffff`` will each
store a PropertyPage containing up to 256 reported values (which
include timestamps and their reporter's identity). Any Transaction
updating the value of a Property first reads out the PropertyContainer
object at ``0000`` and then reads out the appropriate
PropertyPageContainer before adding the update and writing the new
PropertyPageContainer back to state.

The Transaction Processor treats these pages as a ring buffer, so that
when page ``ffff`` is filled, the next update will erase the entries
at page ``0001`` and be stored there, and subsequent page-filling will
continue to overwrite the next oldest page. This ensures no Property
ever runs out of space for new updates. Under this scheme, 16^2 *
(16^4 - 1) = 16776960 entries can be stored before older updates are
overwritten.

Updates to Properties can have one of the following protobuf types:
``bytes``, ``string``, ``sint64``, ``float``, or ``Location`` (see the
section on RecordTypes_ below). The type of an update is indicated by
a tag belonging to the PropertySchema object.

.. code-block:: protobuf

   message Property {
       message Reporter {
           // The public key of the Agent authorized to report updates.
	   string public_key = 1;

	   // A flag indicating whether the reporter is authorized to
	   // send updates. When a reporter is added, this is set to
	   // true, and a `RevokeReporter` transaction sets it to false.
	   bool authorized = 2;

	   // An update must be stored with some way of identifying which
	   // Agent sent it. Storing a full public key for each update would
	   // be wasteful, so instead Reporters are identified by their index
	   // in the `reporters` field.
	   uint32 index = 3;
       }

       // The name of the Property, e.g. "temperature". This must be unique
       // among Properties.
       string name = 1;

       // The natural key of the Property's associated Record.
       string record_id = 2;

       // The Property's type (int, string, etc.)
       PropertySchema.DataType data_type = 3;

       // The Reporters authorized to send updates, sorted by index. New
       // Reporters should be given an index equal to the number of
       // Reporters already authorized.
       repeated Reporter reporters = 4;

       // The page to which new updates are added. This number represents
       // the last 4 hex characters of the page's address. Consequently,
       // it should not exceed 16^4 = 65536.
       uint32 current_page = 5;

       // A flag indicating whether the first 16^4 pages have been filled.
       // This is used to calculate the last four hex characters of the
       // address of the page containing the earliest updates. When it is
       // false, the earliest page's address will end in "0001". When it is
       // true, the earliest page's address will be one more than the
       // current_page, or "0001" if the current_page is "ffff".
       bool wrapped = 6;
   }

   message PropertyPage {
       message ReportedValue {
           // The index of the reporter id in reporters field
           uint32 reporter_index = 1;
           // Approximately when this value was reported, as a Unix UTC timestamp
           uint64 timestamp = 2;

           // The type-specific value of the update. Only one of these
           // fields should be used, and it should match the type
           // specified for this Property in the RecordType.
           bytes bytes_value = 11;
           string string_value = 12;
           sint64 int_value = 13;
           float float_value = 14;
           Location location_value = 15;
       }

       // The name of the page's associated Property and the record_id of
       // its associated Record. These are required to distinguish pages
       // with colliding addresses.
       string name = 1;
       string record_id = 2;

       // ReportedValues are sorted first by timestamp, then by reporter_index.
       repeated ReportedValue reported_values = 4;
   }


Properties and PropertyPages whose addresses collide are stored in
lists alphabetized by Property name.

.. code-block:: protobuf

   message PropertyContainer {
       repeated Property entries = 1;
   }

   message PropertyPageContainer {
       repeated PropertyPage entries = 1;
   }

.. _RecordTypes:

Record Types
------------

In order to validate incoming tracking data, Records are assigned a
RecordType at creation. A RecordType is a user-defined list of
PropertySchemas, each of which has a name and data type.
PropertySchemas may be designated as ``required``. A required Property
must be initialized with a value at the time of a Record's creation.
For example, a ``Fish`` type might list ``species`` as required, but
not ``temperature``, since temperature wouldn't be known until
measurements were taken. Properties not specified at Record creation
are initialized as empty lists.

.. code-block:: protobuf

   message PropertySchema {
       enum DataType {
           BYTES = 0;
	   STRING = 1;
	   INT = 2;
	   FLOAT = 3;
	   LOCATION = 4;
       }

       // The name of the property, e.g. "temperature"
       string name = 1;

       // The Property's type (int, string, etc.)
       DataType data_type = 2;

       // A flag indicating whether initial values must be provided for the
       // Property when a Record is created.
       bool required = 3;
   }


   message RecordType {
       // A unique human-readable designation for the RecordType
       string name = 1;

       repeated PropertySchema properties = 2;
   }


Each Record will have exactly the Properties listed in its type. New
Records cannot be created without a type; consequently, a
type-creation transaction must be executed before any Records can be
created.

RecordTypes whose addresses collide are stored in a list alphabetized
by name.

.. code-block:: protobuf

   message RecordTypeContainer {
       repeated RecordType entries = 1;
   }


Because it is expected to be used for many RecordTypes, a dedicated
Location protobuf message is used, the values of which are latitude
and longitude.

.. code-block:: protobuf

  message Location {
        // Coordinates are expected to be in millionths of a degree
        sint64 latitude = 1;
        sint64 longitude = 2;
  }


Agents
------

Agents are entities that can send transactions affecting Records. This
could include not only humans and companies that act as owners and
custodians of objects being tracked, but also autonomous sensors
sending transactions that update Records' data. All Agents must be
created (registered on-chain) before interacting with Records.

.. code-block:: protobuf

    message Agent {
        // The Agent's public key. This must be unique.
        string public_key = 1;

        // A human-readable name identifying the Agent.
        string name = 2;

        // Approximately when the Agent was registered, as a Unix UTC timestamp
        uint64 timestamp = 3;
    }

Agents whose keys have the same hash are stored in a list alphabetized
by public key.

.. code-block:: protobuf

    message AgentContainer {
        repeated Agent entries = 1;
    }


Proposals
---------

A Proposal is an offer from the owner or custodian of a Record to
authorize another Agent as an owner, custodian, or reporter for that
Record. Proposals are tagged as being for transfer of ownership,
transfer of custodianship, or authorization of a reporter for some
Properties. Proposals are also tagged as being open, accepted,
rejected, or canceled. There cannot be more than one open Proposal for
a specified role for each combination of Record, receiving Agent, and
issuing Agent.

.. code-block:: protobuf

   message Proposal {
       enum Role {
           OWNER = 1;
           CUSTODIAN = 2;
           REPORTER = 3;
       }

       enum Status {
           OPEN = 1;
           ACCEPTED = 2;
           REJECTED = 3;
           CANCELED = 4;
       }

       // The id of the Record with which this Proposal deals
       string record_id = 1;

       // Approximately when this proposal was created, as a Unix UTC timestamp
       uint64 timestamp = 2;

       // The public key of the Agent that created the Proposal
       string issuing_agent = 3;

       // The public key of the Agent to which the Proposal is addressed
       string receiving_agent = 4;

       // Whether the Proposal is for transfer of ownership or
       // custodianship or reporter authorization
       Role role = 5;

       // The names of properties for which the reporter is being authorized
       // (empty for owner or custodian transfers)
       repeated string properties = 6;

       // Whether the Proposal is open, accepted, rejected, or canceled.
       // For a given Record and receiving Agent, there can be only one
       // open Proposal at a time for each role.
       Status status = 7;

       // human-readable terms of transfer
       string terms = 8;
   }


Proposals with the same address are stored in a list sorted
alphabetically first by ``record_id``, then by ``receiving_agent``,
then by ``timestamp`` (earliest to latest).

.. code-block:: protobuf

   message ProposalContainer {
       repeated Proposal entries = 1;
   }

.. _Addressing:

Addressing
----------

T&T objects are stored under the namespace obtained by taking the
first six characters of the SHA-512 hash of the string
``track_and_trade``:

.. code-block:: pycon

   >>> def get_hash(string):
   ...     return hashlib.sha512(string.encode('utf-8')).hexdigest()
   ...
   >>> get_hash('track_and_trade')[:6]
   '1c1108'

After its namespace prefix, the next two characters of a T&T object's
address are a string based on the object's type:

- Agent: ``ae``
- Property / PropertyPage: ``ea``
- Proposal: ``aa``
- Record: ``ec``
- Record Type: ``ee``

The remaining 62 characters of an object's address are determined by
its type:

- Agent: the first 62 characters of the hash of its public key.
- Property: the concatenation of the following:

  - The first 36 characters of the hash of the identifier of its
    associated Record plus the first 22 characters of the hash of its
    Property name.
  - The string ``0000``.

- PropertyPage: the address of the page to which updates are to be
  written is the concatenation of the following:

  - The first 36 characters of the hash of the identifier of its
    associated Record.
  - The first 22 characters of the hash of its Property name.
  - The hex representation of the ``current_page`` of its associated
    Property left-padded to length 4 with 0s.

- Proposal: the concatenation of the following:

  - The first 36 characters of the hash of the identifier of
    its associated Record.
  - The first 22 characters of its ``receiving_agent``.
  - The first 4 characters of the hash of its ``timestamp``.

- Record: the first 62 characters of the hash of its identifier.
- Record Type: the first 62 characters of the hash of the name of the
  type.

For example, if ``fish-456`` is a Record with a ``temperature``
Property and a ``current_page`` of 28, the address for that
PropertyPage is:

.. code-block:: pycon

    >>> get_hash('track_and_trade')[:6] + 'ea'  + get_hash('fish-456')[:36] + get_hash('temperature')[:22] + hex(28)[2:].zfill(4)
    '1c1108ea840d00edc7507ed05cfb86938e3624ada6c7f08bfeb8fd09b963f81f9d001c'


Transactions
============

Transaction Payload
-------------------

All T&T transactions are wrapped in a tagged payload object to allow
for the transaction to be dispatched to appropriate handling logic.

.. code-block:: protobuf

   message TTPayload {
       enum Action {
           CREATE_AGENT = 1;
           CREATE_RECORD = 2;
           FINALIZE_RECORD = 3;
           CREATE_RECORD_TYPE = 4;
           UPDATE_PROPERTIES = 5;
           CREATE_PROPOSAL = 6;
           ANSWER_PROPOSAL = 7;
           REVOKE_REPORTER = 8;
       }

       Action action = 1;

       // Approximately when transaction was submitted, as a Unix UTC timestamp
       uint64 timestamp = 2;

       CreateAgentAction create_agent = 3;
       CreateRecordAction create_record = 4;
       FinalizeRecordAction finalize_record = 5;
       CreateRecordTypeAction create_record_type = 6;
       UpdatePropertiesAction update_properties = 7;
       CreateProposalAction create_proposal = 8;
       AnswerProposalAction answer_proposal = 9;
       RevokeReporterAction revoke_reporter = 10;
   }


Any transaction is invalid if its timestamp is greater than the
validator's system time.


Create Agent
------------

Create an Agent that can interact with Records. The ``signer_pubkey``
in the transaction header is used as the Agent's public key.

.. code-block:: protobuf

   message CreateAgentAction {
      // The human-readable name of the Agent, not necessarily unique
      string name = 1;
   }


A CreateAgent transaction is invalid if there is already an Agent with
the signer's public key or if the name is the empty string.


.. _CreateRecord:

Create Record
-------------

When an Agent creates a Record, the Record is initialized with that
Agent as both owner and custodian. Any Properties required of the
Record by its RecordType must have initial values provided.

.. code-block:: protobuf

   message PropertyValue {
       // The name of the property being set
       string name = 1;
       PropertySchema.DataType data_type = 2;

       // The type-specific value to initialize or update a Property. Only
       // one of these fields should be used, and it should match the type
       // specified for this Property in the RecordType.
       bytes bytes_value = 11;
       string string_value = 12;
       sint64 int_value = 13;
       float float_value = 14;
       Location location_value = 15;
   }

   message CreateRecordAction {
       // The natural key of the Record
       string record_id = 1;

       // The name of the RecordType this Record belongs to
       string record_type = 2;

       repeated PropertyValue properties = 3;
   }


A CreateRecord transaction is invalid if one of the following
conditions occurs:

- The signer is not registered as an Agent.
- The identifier is the empty string.
- The identifier belongs to an existing Record.
- A valid RecordType is not specified.
- Initial values are not provided for all of the Properties specified
  as required by the RecordType.
- Initial values of the wrong type are provided.


Finalize Record
---------------

A FinalizeRecord Transaction sets a Record’s ``final`` flag to true. A
finalized Record and its Properties cannot be updated. A Record cannot
be finalized except by its owner, and cannot be finalized if the owner
and custodian are not the same.

.. code-block:: protobuf

   message FinalizeRecordAction {
       string record_id = 1;
   }


A FinalizeRecord transaction is invalid if one of the following
conditions occurs:

- The Record it targets does not exist.
- The Record it targets is already final.
- The signer is not both the Record's owner and custodian.


Create Record Type
------------------

The payload of the Transaction that creates RecordTypes is the same as
the RecordType object itself: it has a name and a list of Properties.

.. code-block:: protobuf

   message CreateRecordTypeAction {
       string name = 1;

       repeated PropertySchema properties = 2;
   }


A CreateRecordType transaction is invalid if one of the following
conditions occurs:

- The signer is not registered as an Agent.
- Its list of Properties is empty.
- The name of the RecordType is the empty string.
- A RecordType with its name already exists.


Update Properties
-----------------

An UpdateProperties transaction contains a ``record_id`` and a list of
PropertyValues (see CreateRecord_ above). It can only be (validly)
sent by an Agent authorized to report on the Property.

.. code-block:: protobuf

   message UpdatePropertiesAction {
       // The natural key of the Record
       string record_id = 1;

       repeated PropertyValue properties = 2;
   }


An UpdateProperties transaction is invalid if one of the following
conditions occurs:

- The Record does not exist.
- The Record is final.
- Its signer is not authorized to report on that Record.
- None of the provided PropertyValues match the types specified in the
  Record's RecordType.


Create Proposal
---------------

A CreateProposal transaction creates an open Proposal concerning some
Record from the signer to the receiving Agent. This Proposal can be
for transfer of ownership, transfer of custodianship, or authorization
to report. If it is a reporter authorization Proposal, a nonempty list
of Property names must be included.

.. code-block:: protobuf

   message CreateProposalPayload {
       enum Role {
           OWNER = 1;
           CUSTODIAN = 2;
           REPORTER = 3;
       }

       string record_id = 1;

       // The public key of the Agent to whom the Proposal is sent
       // (must be different from the Agent sending the Proposal).
       string receiving_agent = 3;

       repeated string properties = 4;

       Role role = 5;
   }


A CreateProposal transaction is invalid if one of the following
conditions occurs:

- The signer is not the owner and the Proposal is for transfer of
  ownership or reporter authorization.
- The signer is not the custodian and the Proposal is for transfer of
  custodianship.
- The receiving Agent is not registered (the signer must be registered
  as well, but this is implied by the previous two conditions).
- There is already an open Proposal for the Record and receiving Agent
  for the specified role.
- The Record is final.
- The Proposal is for reporter authorization and the list of Property
  names is empty.


Answer Proposal
---------------

An Agent who is the receiving Agent for a Proposal for some Record can
accept or reject that Proposal, marking the Proposal's status as
``accepted`` or ``rejected``. The Proposal's ``issuing_agent`` cannot
accept or reject it, but can cancel it. This will mark the Proposal's
status as ``canceled`` rather than ``rejected``.

.. code-block:: protobuf

   message AnswerProposalPayload {
       enum Role {
           OWNER = 1;
           CUSTODIAN = 2;
           REPORTER = 3;
       }

       enum Response {
           ACCEPT = 1;
           REJECT = 2;
           CANCEL = 3;
       }

       string record_id = 1;
       string receiving_agent = 2;
       Role role = 3;
       Response response = 4;
   }


Proposals can conflict, in the sense that a Record's owner might have
opened ownership transfer Proposals with several Agents at once. These
Proposals will not be closed if one of them is accepted. Instead, an
``accept`` answer will check to verify that the issuing Agent is still
the owner or custodian of the Record.

An AnswerProposal transaction is invalid if one of the following
conditions occurs:

- There is no Proposal for that receiving agent, record, and role.
- The signer is not the receiving or issuing Agent of the Proposal.
- The signer is the receiving Agent and answers ``cancel``.
- The signer is the issuing Agent and answers anything other than
  ``cancel``.
- The response is ``accept``, but the issuing Agent is no longer the
  owner or custodian (as appropriate to the role) of the Record.


Revoke Reporter
---------------

The owner of a Record can send a RevokeReporter transaction to remove
a reporter's authorization to report on one or more Properties for
that Record. This creates a Proposal which is immediately closed and
marked as accepted.

.. code-block:: protobuf

   message RevokeReporterPayload {
       string record_id = 1;
       string reporter_id = 2;

       // the Properties for which the reporter's authorization is revoked
       repeated string properties = 3;
   }

A RevokeReporter transaction is invalid if one of the following
conditions occurs:

- The Record does not exist.
- The Record is final.
- The signer is not the Record's owner.
- The reporter whose authorization is to be revoked is not an
  authorized reporter for the Record.
