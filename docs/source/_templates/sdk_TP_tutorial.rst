{% set short_lang = 'python' %}
{% if language == 'JavaScript' %}
    {% set short_lang = 'js' %}
{% endif -%}

***********************************************
Transaction Processor Tutorial  {{ language }}
***********************************************

Overview
========

This tutorial covers the creation of a new Sawtooth Lake transaction family in
{{ language }}, based on the Sawtooth Lake SDK. We will construct a transaction
handler which implements a distributed version of the multi-player game tic-
tac-toe

.. note::

    The SDK contains a fully-implemented version of tic-tac-toe. This tutorial
    is meant to demonstrate the relevant concepts, rather than to create a
    complete implementation. See the SDK_ for full implemenations in
    multiple languages.

.. _SDK: https://github.com/hyperledger/sawtooth-core/tree/master/sdk

A general description of tic-tac-toe, including the rules, can be found on
Wikipedia at:

    https://en.wikipedia.org/wiki/Tic-tac-toe

A full implementation of the tic-tac-toe transaction family can be found in

.. TEMPLATE Replace path below with language specific path

``/project/sawtooth-core/sdk/examples/xo_python/``.

Prerequisites
=============

This tutorial assumes that you have gone through :doc:`/app_developers_guide/getting_started` and are
familiar with the concepts introduced there.

Prior to going through this tutorial, you should have a working vagrant
environment running to which you can login.  Specific setup instructions are
available in :doc:`/app_developers_guide/getting_started`.

The Transaction Processor
=========================

There are two top-level components of a transaction processor: a processor
class and a handler class. The SDK provides a general-purpose processor class.
The handler class is application-dependent and contains the business logic for
a particular family of transactions. Multiple handlers can be connected to a
processor class.

Handlers get called in two ways: an ``apply`` method and various metadata
methods. The metadata is used to connect the handler to the processor, and
we'll discuss it at the end of this tutorial. The bulk of the handler, however,
is made up of ``apply`` and its helper functions, so that's where we'll start.

The ``apply`` Method
====================

``apply`` gets called with two arguments, ``transaction`` and ``state_store``.
``transaction`` holds the command that is to be executed (e.g. taking a space or
creating a game), while ``state_store`` stores information about the current
state of the game (e.g. the board layout and whose turn it is).

Without yet getting into the details of how this information is encoded, we can
start to think about what ``apply`` needs to do. ``apply`` needs to

1) unpack the command data from the transaction,
2) retrieve the game data from the state store,
3) play the game, and
4) save the updated game data.

Accordingly, a top-down approach to ``apply`` might look like this:

{% if language == 'JavaScript' %}

{% else %}
{# Python code is the default #}

.. code-block:: python

    def apply(self, transaction, state_store):
        signer, game_name, action, space = \
            self._unpack_transaction(transaction)

        board, state, player1, player2 = \
            self._get_state_data(game_name, state_store)

        updated_game_data = self._play_xo(
            board, state,
            player1, player2,
            signer, action, space
        )

        self._store_game_data(game_name, updated_game_data, state_store)

{% endif %}

Note that the third step is the only one that actually concerns tic-tac-toe;
the other three steps all concern the coordination of data.

Data
====

So how do we get data out of the transaction? The transaction consists of a
header and a payload. The header contains the "signer", which is used to
identify the current player. The payload will contain an encoding of the game
name, the action ('create' a game, 'take' a space), and the space (which will
be an empty string if the action isn't 'take'). So our ``_unpack_transaction``
function will look like this:

{% if language == 'JavaScript' %}
{% else %}

.. code-block:: python

    def _unpack_transaction(self, transaction):
        header = TransactionHeader()
        header.ParseFromString(transaction.header)
        signer = header.signer

        try:
            game_name, action, space = self._decode_data(transaction.payload)
        except:
            raise InvalidTransaction("Invalid payload serialization")

        return signer, game_name, action, space

{% endif %}

.. TEMPLATE Replace _get_state_data with language specific name if necessary

Before we say how exactly the transaction payload will be decoded, let's look
at ``_get_state_data``. Now, as far as the handler is concerned, it doesn't
matter how the game data is stored. The only thing that matters is that given a
game name, the state store is able to give back the correct game data. (In our
full XO implementation, the game data is stored in a Merkle-radix tree.)


{% if language == 'JavaScript' %}
(% else %}

.. code-block:: python

    def _get_state_data(self, game_name, state_store):
        game_address = self._make_game_address(game_name)

        state_entries = state_store.get([game_address])

        try:
            return self._decode_data(state_entries[0].data)
        except IndexError:
            return None, None, None, None
        except:
            raise InternalError("Failed to deserialize game data.")


{% endif %}

It doesn't matter what exactly the game address is. By convention, we'll store
game data at an address obtained from hashing the game name prepended with some
constant:

{% if language == 'JavaScript' %}
{% else %}

.. code-block:: python

    def _make_game_address(self, game_name):
        prefix = self._namespace_prefix
        game_name_utf8 = game_name.encode('utf-8')
        return prefix + hashlib.sha512(game_name_utf8).hexdigest()


{% endif %}

Finally, we'll store the game data. To do this, we simply need to encode the
updated state of the game and store it back at the address from which it came.

{% if language == 'JavaScript' %}
{% else %}

.. code-block:: python

    def _store_game_data(self, game_name, game_data, state_store):
        game_address = self._make_game_address(game_name)

        encoded_game_data = self._encode_data(game_data)

        addresses = state_store.set([
            StateEntry(
                address=game_address,
                data=encoded_game_data
            )
        ])

        if len(addresses) < 1:
            raise InternalError("State Error")

{% endif %}

So, how should we encode and decode the data? In fact, we can choose whatever
encoding scheme we want; the data is only going to get read and written by the
handler, so as long as we're consistent, it doesn't matter. In this case, we'll
encode the data as a simple UTF-8 comma-separated value string, but we could
use something more sophisticated, like CBOR or JSON.

{% if language == 'JavaScript' %}
{% else %}

.. code-block:: python

    def _decode_data(self, data):
        return data.decode().split(',')

    def _encode_data(self, data):
        return ','.join(data).encode()

{% endif %}

Playing the Game
================

.. TEMPLATE Replace path below with language specific SDK link.

All that's left to do is describe how to play tic-tac-toe. The details here
are fairly straighforward, and the ``_play_xo`` function could certainly be
implemented in different ways. To see our implementation, go to
``/project/sawtooth-core/sdk/examples/xo_{{short_lang}}``. We choose to
represent the board as a string of length 9, with each character in the string
representing a space taken by X, a space taken by O, or a free space. Updating
the board configuration and the current state of the game proceeds
straightforwardly.

The ``XoTransactionHandler`` Class
==================================

And that's all there is to ``apply``! All that's left to do is set up the
``XoTransactionHandler`` class and its metadata. The metadata is used to
*register* the transaction processor with a validator by sending it information
about what kinds of transactions it can handle.

{% if language == 'JavaScript' %}
{% else %}

.. code-block:: python

    class XoTransactionHandler:
        def __init__(self, namespace_prefix):
            self._namespace_prefix = namespace_prefix

        @property
        def family_name(self):
            return 'xo'

        @property
        def family_versions(self):
            return ['1.0']

        @property
        def encodings(self):
            return ['csv-utf8']

        @property
        def namespaces(self):
            return [self._namespace_prefix]

        def apply(self, transaction, state_store):
            # ...


{% endif %}
