*******************************
Events and Transaction Receipts
*******************************

Hyperledger Sawtooth supports creating and broadcasting events.
This allows applications to do the following:

- Subscribe to events that occur related to the blockchain, such
  as a new block being committed or switching to a new fork.
- Subscribe to application specific events defined by a transaction family.
- Relay information about the execution of a transaction back to
  clients without storing that data in state.

.. image:: ../images/event_subsystem.*
   :width: 80%
   :align: center
   :alt: Event Subsystem

.. _events-reference-label:

Events
======

Events are represented with the following protobuf message:

.. code-block:: protobuf

  message Event {
    // Used to subscribe to events and servers as a hint for how to deserialize
    // event_data and what pairs to expect in attributes.
    string event_type = 1;

    // Transparent data defined by the event_type.
    message Attribute {
      string key = 1;
      string value = 2;
    }
    repeated Attribute attributes = 2;

    // Opaque data defined by the event_type.
    bytes  data = 3;
  }


Events are extracted from other data structures such as blocks or
transaction receipts. In order to treat this extraction uniformly, an
EventExtractor interface is implemented for each event source. The
EventExtractor interface takes a list of EventSubscriptions and will only
generate events that are in the union of all subscriptions. An event is "in a
subscription" if the event's event_type field matches the subscription's
event_type field and the filter's key-value pair (if the subscription has
any filters) matches a key-value pair in the event's attribute field.

.. code-block:: python

  interface EventExtractor:
    // Construct all the events of interest by taking the union of all subscriptions.
    // One extractor should be created for each input source that events can be
    // extracted from. This input source should be passed to the implementation through
    // the constructor.
    extract(list<EventSubscription> subscriptions) -> list<Event>

  // If no subscriptions of a given event_type are passed to EventExtractor.extract,
  // the extractor does not need to return events of that type.
  class EventSubscription:
    string event_type
    list<EventFilter> filters

The following filters are implemented:

SIMPLE_ANY
  Represents a subset of events within an event type.

  Since multiple event attributes with the same key can be present in an
  event, an event is considered part of this filter if its match string matches
  the value of ANY attribute with the filter's key.

  For example, if an event has the following attributes:

      - Attribute(key="address", value="abc")
      - Attribute(key="address", value="def")

  it will pass the following filter:

      SimpleAnyFilter(key="address", match_string="abc")

  Because it matches one of the two attributes with the key "address".

SIMPLE_ALL
  Represents a subset of events within an event type.

  Since multiple event attributes with the same key can be present in an
  event, an event is considered part of this filter if its match string matches
  the value of ALL attribute with the filter's key.

  For example, if an event has the following attributes:

      - Attribute(key="address", value="abc")
      - Attribute(key="address", value="def")

  it will NOT pass this filter:

      SimpleAllFilter(key="address", value="abc")

  Because it does not match all attributes with the key "address".

REGEX_ANY
  Represents a subset of events within an event type. Pattern must be a
  valid regular expression that can be compiled by the re module.

  Since multiple event attributes with the same key can be present in an
  event, an event is considered part of this filter if its pattern matches
  the value of ANY attribute with the filter's key.

  For example, if an event has the following attributes:

      - Attribute(key="address", value="abc")
      - Attribute(key="address", value="def")

  it will pass the following filter:

      AnyRegexFilter(key="address", value="abc")

  Because it matches one of the two attributes with the key "address".

REGEX_ALL
  Represents a subset of events within an event type. Pattern must be a
  valid regular expression that can be compiled by the re module.

  Since multiple event attributes with the same key can be present in an
  event, an event is considered part of this filter if its pattern matches
  the value of ALL attribute with the filter's key.

  For example, if an event has the following attributes:

      - Attribute(key="address", value="abc")
      - Attribute(key="address", value="def")

  it will NOT pass this filter:

      AllRegexFilter(key="address", value="abc")

  Because it does not match all attributes with the key "address".

An EventBroadcaster manages external event subscriptions and forwards events to
subscribers as they occur. In order for the EventBroadcaster to learn about
events, the ChainController class implements the Observer pattern. The
ChainController acts as the subject and observers of the ChainController
implement the ChainObserver interface.

.. code-block:: python

  interface ChainObserver:
    // This method is called by the ChainController on block boundaries.
    chain_update(Block block, list<TransactionReceipt> receipts)

  class EventBroadcaster:
    // Register the subscriber for the given event subscriptions and begin sending it
    // events on block boundaries.
    //
    // If any of the block ids in last_known_block_ids are part of the current chain,
    // the observer will be notified of all events that it would have received based on
    // its subscriptions for each block in the chain since the most recent
    // block in last_known_block_ids.
    //
    // Raises an exception if:
    // 1. The subscription is unsuccessful.
    // 2. None of the block ids in last_known_block_ids are part of the current chain.
    add_subscriber(string connection_id, list<EventSubscription> subscriptions,
                   list<string> last_known_block_ids)

    // Stop sending events to the subscriber
    remove_subscriber(string connection_id)

    // Notify all observers of all events they are subscribed to.
    chain_update(Block block, list<TransactionReceipt> receipts)


On receiving a chain_update() notification from the ChainController, the
EventBroadcaster instantiates a new EventExtractor, passes each extractor all
the EventSubscriptions for all subscribers, and receives the list of events
that is the union of the events that all subscribers are interested in. The
EventBroadcaster then distributes the events to each subscriber based on
the subscriber's list of subscriptions.

To reduce the number of messages sent to subscribers, multiple Event messages
are wrapped in an EventList message when possible:

.. code-block:: python

  EventList {
    repeated Event events = 1;
  }

ClientEventSubscribeRequest messages are sent by external clients to the
validator in order to subscribe to events. ClientEventSubscribeResponse messages
are sent by the validator to the client in response to notify the client whether
their subscription was successful. When an external client subscribes to events,
they may optionally send a list of block ids along with their subscriptions. If
any of the blocks sent are in the current chain, the EventBroadcaster will bring
the client up to date by sending it events for all blocks since the most recent
block sent with the subscribe request.

.. code-block:: protobuf

  message ClientEventsSubscribeRequest {
      repeated EventSubscription subscriptions = 1;
      // The block id (or ids, if trying to walk back a fork) the subscriber last
      // received events on. It can be set to empty if it has not yet received the
      // genesis block.
      repeated string last_known_block_ids = 2;
  }

  message ClientEventsSubscribeResponse {
      enum Status {
           OK = 0;
           INVALID_FILTER = 1;
           UNKNOWN_BLOCK = 2;
      }
      Status status = 1;
      // Additional information about the response status
      string response_message = 2;
  }

Event Extractors
----------------

Two event extractors are created to extract events from blocks and
transaction receipts: BlockEventExtractor and ReceiptEventExtractor. The
BlockEventExtractor will extract events of type "sawtooth/block-commit". The
ReceiptEventExtractor will extract events of type "sawtooth/state-delta" and
events defined by transaction families.

Example events generated by BlockEventExtractor:

.. code-block:: protobuf

  // Example sawtooth/block-commit event
  Event {
    event_type = "sawtooth/block-commit",
    attributes = [
      Attribute { key = "block_id", value = "abc...123" },
      Attribute { key = "block_num", value = "523" },
      Attribute { key = "state_root_hash", value = "def...456" },
      Attribute { key = "previous_block_id", value = "acf...146" },
    ],
  }

Example events generated by ReceiptEventExtractor:

.. code-block:: protobuf


  // Example transaction family specific event
  Event {
    event_type = "xo/create",
    attributes = [Attribute { key = "game_name", value = "game0" }],
  }

  // Example sawtooth/block-commit event
  Event {
    event_type = "sawtooth/state-delta",
    attributes = [Attribute { key = "address", value = "abc...def" }],
    event_data = <bytes>
  }


Transaction Receipts
====================

Transaction receipts provide clients with information that is related to the
execution of a transaction but should not be stored in state, such as:

   - Whether the transaction was valid
   - How the transaction changed state
   - Events of interest that occurred during execution of the transaction
   - Other transaction-family-specific execution information

Transaction receipts can also provide the validator with information about
transaction execution without re-executing the transaction.

Sawtooth transaction receipts are represented as a protobuf message when exposed
to clients. A transaction receipt contains a list of StateChange messages, a
list of Event messages, and a list of TransactionReceipt.Data messages:

.. code-block:: protobuf

  message TransactionReceipt {
    // State changes made by this transaction
    // StateChange is already defined in protos/state_delta.proto
    repeated StateChange state_changes = 1;
    // Events fired by this transaction
    repeated Event events = 2;
    // Transaction family defined data
    repeated bytes data = 3;

    string transaction_id = 4;
  }

The fields in the TransactionReceipt.Data are opaque to Sawtooth and their
interpretation is left up to the transaction family. TransactionReceipt.Data
can be requested for a transaction that has been committed and should only be
used to store information about a transaction’s execution that should not be
kept in state.  Clients can use the event system described above to subscribe to
events produced by transaction processors.

Transaction Receipt Store
-------------------------

The TransactionReceiptStore class stores receipts. New receipts are written to
the TransactionReceiptStore after a block is validated.

Transaction receipts will only be stored in this off-chain store and will not
be included in the block. Note that because a transaction may exist in multiple
blocks at a time, the transaction receipt is stored by both transaction id and
block state root hash.

.. code-block:: python

  class TransactionReceiptStore:
  	def put_receipt(self, txn_id, receipt):
      	"""Add the given transaction receipt to the store. Does not guarantee
         	it has been written to the backing store.

      	Args:
          	txn_id (str): the id of the transaction being stored.
          	state_root_hash: the state root of the block this transaction was
            executed in.
          	receipt (TransactionReceipt): the receipt object to store.
      	"""

  	def get_receipt(self, txn_id):
      	"""Returns the TransactionReceipt

      	Args:
          	txn_id (str): the id of the transaction for which the receipt
            should be retrieved.
          	state_root_hash: the state root of the block this transaction was
            executed in.

      	Returns:
          	TransactionReceipt: The receipt for the given transaction id.

      	Raises:
          	KeyError: if the transaction id is unknown.
      	"""

Message Handlers
----------------

Once transaction receipts are stored in the TransactionReceiptStore, clients
can request a transaction receipt for a given transaction id.

.. code-block:: protobuf

  // Fetches a specific txn by its id (header_signature) from the blockchain.
  message ClientReceiptGetRequest {
      repeated string transaction_ids = 1;
  }

  // A response that returns the txn receipt specified by a
  // ClientReceiptGetRequest.
  //
  // Statuses:
  //   * OK - everything worked as expected, txn receipt has been fetched
  //   * INTERNAL_ERROR - general error, such as protobuf failing to deserialize
  //   * NO_RESOURCE - no receipt exists for the transaction id specified
  message ClientReceiptGetResponse {
      enum Status {
          OK = 0;
          INTERNAL_ERROR = 1;
          NO_RESOURCE = 4;
      }
      Status status = 1;
      repeated TransactionReceipt receipts = 2;

To request a transaction receipt from the REST API, pass the transaction ID in the form
``http://rest-api:8008/receipts/?id=TRANSACTION-ID`` where ``TRANSACTION-ID`` is your 128-character transaction ID.  Use ``localhost:8008`` if the Validator is running on Ubuntu instead of Docker.


.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
