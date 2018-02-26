{% set short_lang = 'python' %}
{% if language == 'JavaScript' %}
    {% set short_lang = 'js' %}
{% elif language == 'Go' %}
    {% set short_lang = 'go' %}
{% endif %}

{% set lowercase_lang = 'python' %}
{% if language == 'JavaScript' %}
    {% set lowercase_lang = 'javascript' %}
{% elif language == 'Go' %}
    {% set lowercase_lang = 'go' %}
{% endif %}

*****************************************************
Transaction Processor: Creating a Transaction Handler
*****************************************************

A transaction processor has two top-level components:

* Processor class. The SDK provides a general-purpose processor class.

* Handler class. The handler class is application-dependent. It contains the
  business logic for a particular family of transactions. Multiple handlers
  can be connected to an instance of the processor class.

Entry Point
===========

Since a transaction processor is a long running process, it must have an
entry point.

In the entry point, the ``TransactionProcessor`` class is given the address
to connect with the validator and the handler class.

{% if language == 'JavaScript' %}

.. code-block:: javascript
    :caption: a simplified xo_javascript/index.js

    const { TransactionProcessor } = require('sawtooth-sdk/processor')
    const XOHandler = require('./xo_handler')

    // In docker, the address would be the validator's container name
    // with port 4004
    const address = 'tcp://127.0.0.1:4004'
    const transactionProcessor = new TransactionProcessor(address)

    transactionProcessor.addHandler(new XOHandler())

    transactionProcessor.start()

{% elif language == 'Go' %}

.. code-block:: go
    :caption: a simplified sawtooth_xo/main.go

    import (
        "sawtooth_sdk/processor"
        xo "sawtooth_xo/handler"
        "syscall"
    )

    func main() {

        endpoint := "tcp://127.0.0.1:4004"
        // In docker, endpoint would be the validator's container name
        // with port 4004
        handler := &xo.XoHandler{}
        processor := processor.NewTransactionProcessor(endpoint)
        processor.AddHandler(handler)
        processor.ShutdownOnSignal(syscall.SIGINT, syscall.SIGTERM)

        processor.Start()
    }

{% else %}

.. code-block:: python
    :caption: a simplified sawtooth_xo/processor/main.py

    from sawtooth_sdk.processor.core import TransactionProcessor
    from sawtooth_xo.processor.handler import XoTransactionHandler

    def main():
        # In docker, the url would be the validator's container name with
        # port 4004
        processor = TransactionProcessor(url='tcp://127.0.0.1:4004')

        handler = XoTransactionHandler()

        processor.add_handler(handler)

        processor.start()

{% endif %}

Handlers get called in two ways: with an ``apply`` method and with various
"metadata" methods. The metadata is used to connect the handler to the
processor. The bulk of the handler, however, is made up of ``apply`` and its
helper functions.

{% if language == 'JavaScript' %}

.. code-block:: javascript
    :caption: xo_javascript/xo_handler.js XOHandler class

    class XOHandler extends TransactionHandler {
      constructor () {
        super(XO_FAMILY, '1.0', 'csv-utf8', [XO_NAMESPACE])
      }

      apply (transactionProcessRequest, stateStore) {
        //

Note that the ``XOHandler`` class extends the ``TransactionHandler`` class defined in the
JavaScript SDK.

{% elif language == 'Go' %}

.. code-block:: go
    :caption: sawtooth_xo/handler/handler.go XoHandler struct

    type XoHandler struct {
    }

    func (self *XoHandler) FamilyName() string {
        return "xo"
    }

    func (self *XoHandler) FamilyVersions() []string {
        return []string{"1.0"}
    }

    func (self *XoHandler) Namespaces() []string {
        return []string{xo_state.Namespace}
    }

    func (self *XoHandler) Apply(request *processor_pb2.TpProcessRequest, context *processor.Context) error {

{% else %}

.. code-block:: python
    :caption: sawtooth_xo/processor/handler.py XoTransactionHandler class

    class XoTransactionHandler(TransactionHandler):
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

        def apply(self, transaction, context):
            # ...

Note that the ``XoTransactionHandler`` extends the ``TransactionHandler`` defined
in the Python SDK.

{% endif %}

The ``apply`` Method
====================

{% if language == 'JavaScript' %}
``apply`` gets called with two arguments, ``transactionProcessRequest`` and ``stateStore``.
``transactionProcessRequest`` holds the command that is to be executed (e.g. taking a space or
creating a game), while ``stateStore`` stores information about the current
state of the game (e.g. the board layout and whose turn it is).

The transaction contains payload bytes that are opaque to the validator core,
and transaction family specific. When implementing a transaction handler the
binary serialization protocol is up to the implementer.

{% elif language == 'Go' %}
``apply`` gets called with two arguments, ``request`` and ``context``.
``request`` holds the command that is to be executed (e.g. taking a space or
creating a game), while ``context`` stores information about the current
state of the game (e.g. the board layout and whose turn it is).

The transaction contains payload bytes that are opaque to the validator core,
and transaction family specific. When implementing a transaction handler the
binary serialization protocol is up to the implementer.

{% else %}
``apply`` gets called with two arguments, ``transaction`` and
``context``. The argument ``transaction`` is an instance of the class
Transaction that is created from the  protobuf definition. Also,
``context`` is an instance of the class Context from the  python SDK.

``transaction`` holds the command that is to be executed (e.g. taking a space or
creating a game), while ``context`` stores information about the current
state of the game (e.g. the board layout and whose turn it is).

The transaction contains payload bytes that are opaque to the validator core,
and transaction family specific. When implementing a transaction handler the
binary serialization protocol is up to the implementer.
{% endif %}

To separate details of state encoding and payload handling from validation
logic, the XO example has ``XoState`` and ``XoPayload`` classes. The ``XoPayload`` has
name, action, and space fields, while the ``XoState`` contains information about
the game name, board, state, and which players are playing in the game.

Valid actions are: create a new game, take an unoccupied space, and delete a game.

{% if language == 'JavaScript' %}

.. code-block:: javascript
    :caption: xo_javascript/xo_handler.js apply overview


    apply (transactionProcessRequest, context) {
        let payload = XoPayload.fromBytes(transactionProcessRequest.payload)
        let xoState = new XoState(context)
        let header = transactionProcessRequest.header
        let player = header.signerPublicKey
        if (payload.action === 'create') {
            ...
        } else if (payload.action === 'take') {
            ...
        } else if (payload.action === 'delete') {
            ...
        } else {
            throw new InvalidTransaction(
                `Action must be create, delete, or take not ${payload.action}`
            )
        }
    }

{% elif language == 'Go' %}

.. code-block:: go
    :caption: sawtooth_xo/handler/handler.go apply overview

    func (self *XoHandler) Apply(request *processor_pb2.TpProcessRequest, context *processor.Context) error {
        // The xo player is defined as the signer of the transaction, so we unpack
        // the transaction header to obtain the signer's public key, which will be
        // used as the player's identity.
        header := request.GetHeader()
        player := header.GetSignerPublicKey()

        // The payload is sent to the transaction processor as bytes (just as it
        // appears in the transaction constructed by the transactor).  We unpack
        // the payload into an XoPayload struct so we can access its fields.
        payload, err := xo_payload.FromBytes(request.GetPayload())
        if err != nil {
            return err
        }

        xoState := xo_state.NewXoState(context)

        switch payload.Action {
        case "create":
            ...
        case "delete":
            ...
        case "take":
            ...
        default:
            return &processor.InvalidTransaction{
                Msg: fmt.Sprintf("Invalid Action : '%v'", payload.Action)}
        }

{% else %}

{# Python code is the default #}

.. code-block:: python
    :caption: sawtooth_xo/processor/handler.py apply overview

    def apply(self, transaction, context):

        header = transaction.header
        signer = header.signer_public_key

        xo_payload = XoPayload.from_bytes(transaction.payload)

        xo_state = XoState(context)

        if xo_payload.action == 'delete':
            ...
        elif xo.payload.action == 'create':
            ...
        elif xo.payload.action == 'take':
            ...
        else:
            raise InvalidTransaction('Unhandled action: {}'.format(
                xo_payload.action))

{% endif %}

For every new payload, the transaction processor validates rules surrounding the
action. If all of the rules validate, then
state is updated based on whether we are creating a game, deleting a game, or updating the
game by taking a space.


Game Logic
==========

The XO game logic is described in the XO transaction family specification;
see :ref:`xo-execution-label`.

The validation rules and state updates that are associated with the ``create``,
``delete``, and ``take`` actions are shown below.

Create
------

The ``create`` action has the following implementation:
{% if language == 'JavaScript' %}

.. code-block:: javascript
    :caption: xo_javascript/xo_handler.js apply 'create'

    if (payload.action === 'create') {
      return xoState.getGame(payload.name)
        .then((game) => {
          if (game !== undefined) {
            throw new InvalidTransaction('Invalid Action: Game already exists.')
          }

          let createdGame = {
            name: payload.name,
            board: '---------',
            state: 'P1-NEXT',
            player1: '',
            player2: ''
          }

          _display(`Player ${player.toString().substring(0, 6)} created game ${payload.name}`)

          return xoState.setGame(payload.name, createdGame)
        })
    }

{% elif language == 'Go' %}

.. code-block:: go
    :caption: sawtooth_xo/handler/handler.go apply 'create'

    case "create":
		err := validateCreate(xoState, payload.Name)
		if err != nil {
			return err
		}
		game := &xo_state.Game{
			Board:   "---------",
			State:   "P1-NEXT",
			Player1: "",
			Player2: "",
			Name:    payload.Name,
		}
		displayCreate(payload, player)
        return xoState.SetGame(payload.Name, game)

``validateCreate`` is defined as follows:

.. code-block:: go

    func validateCreate(xoState *xo_state.XoState, name string) error {
        game, err := xoState.GetGame(name)
        if err != nil {
            return err
        }
        if game != nil {
            return &processor.InvalidTransactionError{Msg: "Game already exists"}
        }

        return nil
    }
{% else %}

.. code-block:: python
    :caption: sawtooth_xo/processor/handler.py apply 'create'

    elif xo_payload.action == 'create':

        if xo_state.get_game(xo_payload.name) is not None:
            raise InvalidTransaction(
                'Invalid action: Game already exists: {}'.format(
                    xo_payload.name))

        game = Game(name=xo_payload.name,
                    board="-" * 9,
                    state="P1-NEXT",
                    player1="",
                    player2="")

        xo_state.set_game(xo_payload.name, game)
        _display("Player {} created a game.".format(signer[:6]))

{% endif %}

Delete
------

The ``delete`` action has the following implementation:
{% if language == 'JavaScript' %}

.. code-block:: javascript
    :caption: xo_javascript/xo_handler.js apply 'delete'

    if (payload.action === 'delete') {
      return xoState.getGame(payload.name)
        .then((game) => {
          if (game === undefined) {
            throw new InvalidTransaction(
              `No game exists with name ${payload.name}: unable to delete`)
          }
          return xoState.deleteGame(payload.name)
        })
    } else {
      throw new InvalidTransaction(
        `Action must be create or take not ${payload.action}`
      )
    }

{% elif language == 'Go' %}

.. code-block:: go
    :caption: sawtooth_xo/handler/handler.go apply 'delete'

    case "delete":
		err := validateDelete(xoState, payload.Name)
		if err != nil {
			return err
		}
        return xoState.DeleteGame(payload.Name)

``validateDelete`` is defined as follows:

.. code-block:: go

    func validateDelete(xoState *xo_state.XoState, name string) error {
        game, err := xoState.GetGame(name)
        if err != nil {
            return err
        }
        if game == nil {
            return &processor.InvalidTransactionError{Msg: "Delete requires an existing game"}
        }
        return nil
    }

{% else %}

.. code-block:: python
    :caption: sawtooth_xo/processor/handler.py apply 'delete'


    if xo_payload.action == 'delete':
        game = xo_state.get_game(xo_payload.name)

        if game is None:
            raise InvalidTransaction(
                'Invalid action: game does not exist')

        xo_state.delete_game(xo_payload.name)
{% endif %}

Take
----

The ``take`` action has the following implementation:

{% if language == 'JavaScript' %}

.. code-block:: none
    :caption: xo_javascript/xo_handler.js apply 'take'

    if (payload.action === 'take') {
      return xoState.getGame(payload.name)
        .then((game) => {
          try {
            parseInt(payload.space)
          } catch (err) {
            throw new InvalidTransaction('Space could not be converted as an integer.')
          }

          if (payload.space < 1 || payload.space > 9) {
            throw new InvalidTransaction('Invalid space ' + payload.space)
          }

          if (game === undefined) {
            throw new InvalidTransaction(
              'Invalid Action: Take requires an existing game.'
            )
          }
          if (['P1-WIN', 'P2-WIN', 'TIE'].includes(game.state)) {
            throw new InvalidTransaction('Invalid Action: Game has ended.')
          }

          if (game.player1 === '') {
            game.player1 = player
          } else if (game.player2 === '') {
            game.player2 = player
          }
          let boardList = game.board.split('')

          if (boardList[payload.space - 1] !== '-') {
            throw new InvalidTransaction('Invalid Action: Space already taken.')
          }

          if (game.state === 'P1-NEXT' && player === game.player1) {
            boardList[payload.space - 1] = 'X'
            game.state = 'P2-NEXT'
          } else if (
            game.state === 'P2-NEXT' &&
            player === game.player2
          ) {
            boardList[payload.space - 1] = 'O'
            game.state = 'P1-NEXT'
          } else {
            throw new InvalidTransaction(
              `Not this player's turn: ${player.toString().substring(0, 6)}`
            )
          }

          game.board = boardList.join('')

          if (_isWin(game.board, 'X')) {
            game.state = 'P1-WIN'
          } else if (_isWin(game.board, 'O')) {
            game.state = 'P2-WIN'
          } else if (game.board.search('-') === -1) {
            game.state = 'TIE'
          }

          let playerString = player.toString().substring(0, 6)

          _display(
            `Player ${playerString} takes space: ${payload.space}\n\n` +
              _gameToStr(
                game.board,
                game.state,
                game.player1,
                game.player2,
                payload.name
              )
          )

          return xoState.setGame(payload.name, game)
        })
    }

{% elif language == 'Go' %}

.. code-block:: go
    :caption: sawtooth_xo/handler/handler.go apply 'take'

    case "take":
		err := validateTake(xoState, payload, player)
		if err != nil {
			return err
		}
		game, err := xoState.GetGame(payload.Name)
		if err != nil {
			return err
		}
		// Assign players if new game
		if game.Player1 == "" {
			game.Player1 = player
		} else if game.Player2 == "" {
			game.Player2 = player
		}

		if game.State == "P1-NEXT" && player == game.Player1 {
			boardRunes := []rune(game.Board)
			boardRunes[payload.Space-1] = 'X'
			game.Board = string(boardRunes)
			game.State = "P2-NEXT"
		} else if game.State == "P2-NEXT" && player == game.Player2 {
			boardRunes := []rune(game.Board)
			boardRunes[payload.Space-1] = 'O'
			game.Board = string(boardRunes)
			game.State = "P1-NEXT"
		} else {
			return &processor.InvalidTransactionError{
				Msg: fmt.Sprintf("Not this player's turn: '%v'", player)}
		}

		if isWin(game.Board, 'X') {
			game.State = "P1-WIN"
		} else if isWin(game.Board, 'O') {
			game.State = "P2-WIN"
		} else if !strings.Contains(game.Board, "-") {
			game.State = "TIE"
		}
		displayTake(payload, player, game)
        return xoState.SetGame(payload.Name, game)

``validateTake`` is defined as follows:

.. code-block:: go

    func validateTake(xoState *xo_state.XoState, payload *xo_payload.XoPayload, signer string) error {
        game, err := xoState.GetGame(payload.Name)
        if err != nil {
            return err
        }
        if game == nil {
            return &processor.InvalidTransactionError{Msg: "Take requires an existing game"}
        }
        if game.State == "P1-WIN" || game.State == "P2-WIN" || game.State == "TIE" {
            return &processor.InvalidTransactionError{Msg: "Game has ended"}
        }

        if game.State == "P1-WIN" || game.State == "P2-WIN" || game.State == "TIE" {
            return &processor.InvalidTransactionError{
                Msg: "Invalid Action: Game has ended"}
        }

        if game.Board[payload.Space-1] != '-' {
            return &processor.InvalidTransactionError{Msg: "Space already taken"}
        }
        return nil
    }

{% else %}

.. code-block:: python
    :caption: sawtooth_xo/processor/handler.py apply 'take'

    elif xo_payload.action == 'take':
        game = xo_state.get_game(xo_payload.name)

        if game is None:
            raise InvalidTransaction(
                'Invalid action: Take requires an existing game')

        if game.state in ('P1-WIN', 'P2-WIN', 'TIE'):
            raise InvalidTransaction('Invalid Action: Game has ended')

        if (game.player1 and game.state == 'P1-NEXT' and
            game.player1 != signer) or \
                (game.player2 and game.state == 'P2-NEXT' and
                    game.player2 != signer):
            raise InvalidTransaction(
                "Not this player's turn: {}".format(signer[:6]))

        if game.board[xo_payload.space - 1] != '-':
            raise InvalidTransaction(
                'Invalid Action: space {} already taken'.format(
                    xo_payload))

        if game.player1 == '':
            game.player1 = signer

        elif game.player2 == '':
            game.player2 = signer

        upd_board = _update_board(game.board,
                                    xo_payload.space,
                                    game.state)

        upd_game_state = _update_game_state(game.state, upd_board)

        game.board = upd_board
        game.state = upd_game_state

        xo_state.set_game(xo_payload.name, game)
        _display(
            "Player {} takes space: {}\n\n".format(
                signer[:6],
                xo_payload.space) +
            _game_data_to_str(
                game.board,
                game.state,
                game.player1,
                game.player2,
                xo_payload.name))

{% endif %}

Payload
=======

.. note::

    :doc:`/architecture/transactions_and_batches` contains a detailed
    description of how transactions are structured and used. Please read
    this document before proceeding, if you have not reviewed it.

So how do we get data out of the transaction? The transaction consists of a
header and a payload. The header contains the "signer", which is used to
identify the current player. The payload will contain an encoding of the game
name, the action (``create`` a game, ``delete`` a game, ``take`` a space), and
the space (which will be an empty string if the action isn't ``take``).

An XO transaction request payload consists of the UTF-8 encoding of a
string with exactly two commas, formatted as follows:

``<name>,<action>,<space>``

where

* <name> is a nonempty string not containing the character ``|``
* <action> is either ``take`` or ``create``
* <space> is an integer strictly between 0 and 10 if the action is ``take``

{% if language == 'JavaScript' %}

.. code-block:: javascript
    :caption: xo_javascript/xo_payload.js

    class XoPayload {
        constructor (name, action, space) {
            this.name = name
            this.action = action
            this.space = space
        }

        static fromBytes (payload) {
            payload = payload.toString().split(',')
            if (payload.length === 3) {
                let xoPayload = new XoPayload(payload[0], payload[1], payload[2])
                if (!xoPayload.name) {
                    throw new InvalidTransaction('Name is required')
                }
                if (xoPayload.name.indexOf('|') !== -1) {
                    throw new InvalidTransaction('Name cannot contain "|"')
                }

                if (!xoPayload.action) {
                    throw new InvalidTransaction('Action is required')
                }
                return xoPayload
            } else {
            throw new InvalidTransaction('Invalid payload serialization')
            }
        }
    }

{% elif language == 'Go' %}

.. code-block:: go
    :caption: sawtooth_xo/xo_payload/xo_payload.go

    type XoPayload struct {
        Name   string
        Action string
        Space  int
    }

    func FromBytes(payloadData []byte) (*XoPayload, error) {
        if payloadData == nil {
            return nil, &processor.InvalidTransactionError{Msg: "Must contain payload"}
        }

        parts := strings.Split(string(payloadData), ",")
        if len(parts) != 3 {
            return nil, &processor.InvalidTransactionError{Msg: "Payload is malformed"}
        }

        payload := XoPayload{}
        payload.Name = parts[0]
        payload.Action = parts[1]

        if len(payload.Name) < 1 {
            return nil, &processor.InvalidTransactionError{Msg: "Name is required"}
        }

        if len(payload.Action) < 1 {
            return nil, &processor.InvalidTransactionError{Msg: "Action is required"}
        }

        if payload.Action == "take" {
            space, err := strconv.Atoi(parts[2])
            if err != nil {
                return nil, &processor.InvalidTransactionError{
                    Msg: fmt.Sprintf("Invalid Space: '%v'", parts[2])}
            }
            payload.Space = space
        }

        if strings.Contains(payload.Name, "|") {
            return nil, &processor.InvalidTransactionError{
                Msg: fmt.Sprintf("Invalid Name (char '|' not allowed): '%v'", parts[2])}
        }

        return &payload, nil
    }


{% else %}

.. code-block:: python
    :caption: sawtooth_xo/processor/xo_payload.py

    class XoPayload(object):

        def __init__(self, payload):
            try:
                # The payload is csv utf-8 encoded string
                name, action, space = payload.decode().split(",")
            except ValueError:
                raise InvalidTransaction("Invalid payload serialization")

            if not name:
                raise InvalidTransaction('Name is required')

            if '|' in name:
                raise InvalidTransaction('Name cannot contain "|"')

            if not action:
                raise InvalidTransaction('Action is required')

            if action not in ('create', 'take', 'delete'):
                raise InvalidTransaction('Invalid action: {}'.format(action))

            if action == 'take':
                try:

                    if int(space) not in range(1, 10):
                        raise InvalidTransaction(
                            "Space must be an integer from 1 to 9")
                except ValueError:
                    raise InvalidTransaction(
                        'Space must be an integer from 1 to 9')

            if action == 'take':
                space = int(space)

            self._name = name
            self._action = action
            self._space = space

        @staticmethod
        def from_bytes(payload):
            return XoPayload(payload=payload)

        @property
        def name(self):
            return self._name

        @property
        def action(self):
            return self._action

        @property
        def space(self):
            return self._space

{% endif %}

State
=====

The XoState class turns game information into bytes and stores it in the validator's Radix-Merkle tree,
turns bytes stored in the validator's Radix-Merkle tree into game information, and does these
operations with a state storage scheme that handles hash collisions.

An XO state entry consists of the UTF-8 encoding of a string with
exactly four commas formatted as follows:

``<name>,<board>,<game-state>,<player-key-1>,<player-key-2>``

where

* <name> is a nonempty string not containing `|`,
* <board> is a string of length 9 containing only `O`, `X`, or `-`,
* <game-state> is one of the following: `P1-NEXT`, `P2-NEXT`, `P1-WIN`,
* `P2-WIN`, or `TIE`, and
* <player-key-1> and <player-key-2> are the (possibly empty) public keys
* associated with the game's players.

In the event of a hash collision (i.e. two or more state entries
sharing the same address), the colliding state entries will stored as
the UTF-8 encoding of the string ``<a-entry>|<b-entry>|...``, where
<a-entry>, <b-entry>,... are sorted alphabetically.

{% if language == 'JavaScript' %}

.. code-block:: javascript
    :caption: xo_javascript/xo_state.js

    class XoState {
        constructor (context) {
            this.context = context
            this.addressCache = new Map([])
            this.timeout = 500 // Timeout in milliseconds
        }

        getGame (name) {
            return this._loadGames(name).then((games) => games.get(name))
        }
  
        setGame (name, game) {
            let address = _makeXoAddress(name)

            return this._loadGames(name).then((games) => {
                games.set(name, game)
                return games
            }).then((games) => {
                let data = _serialize(games)

                this.addressCache.set(address, data)
                let entries = {
                    [address]: data
                }
                return this.context.setState(entries, this.timeout)
            })
        }

        deleteGame (name) {
            let address = _makeXoAddress(name)
            return this._loadGames(name).then((games) => {
                games.delete(name)

                if (games.size === 0) {
                    this.addressCache.set(address, null)
                    return this.context.deleteState([address], this.timeout)
                } else {
                    let data = _serialize(games)
                    this.addressCache.set(address, data)
                    let entries = {
                        [address]: data
                    }
                        return this.context.setState(entries, this.timeout)
                    }
                })
            }

        _loadGames (name) {
            let address = _makeXoAddress(name)
            if (this.addressCache.has(address)) {
                if (this.addressCache.get(address) === null) {
                    return Promise.resolve(new Map([]))
                } else {
                    return Promise.resolve(_deserialize(this.addressCache.get(address)))
                }
            } else {
                return this.context.getState([address], this.timeout)
                    .then((addressValues) => {
                        if (!addressValues[address].toString()) {
                            this.addressCache.set(address, null)
                            return new Map([])
                        } else {
                            let data = addressValues[address].toString()
                            this.addressCache.set(address, data)
                            return _deserialize(data)
                        }
                    })
                }
            }
        }

    const _hash = (x) =>
        crypto.createHash('sha512').update(x).digest('hex').toLowerCase().substring(0, 64)

    const XO_FAMILY = 'xo'

    const XO_NAMESPACE = _hash(XO_FAMILY).substring(0, 6)

    const _deserialize = (data) => {
        let gamesIterable = data.split('|').map(x => x.split(','))
            .map(x => [x[0], {name: x[0], board: x[1], state: x[2], player1: x[3], player2: x[4]}])
        return new Map(gamesIterable)
    }

    const _serialize = (games) => {
        let gameStrs = []
        for (let nameGame of games) {
            let name = nameGame[0]
            let game = nameGame[1]
            gameStrs.push([name, game.board, game.state, game.player1, game.player2].join(','))
        }

        gameStrs.sort()

        return Buffer.from(gameStrs.join('|'))
    }

{% elif language == 'Go' %}

.. code-block:: go
    :caption: sawtooth_xo/xo_state/xo_state.go

    var Namespace = hexdigest("xo")[:6]

    type Game struct {
        Board   string
        State   string
        Player1 string
        Player2 string
        Name    string
    }

    // XoState handles addressing, serialization, deserialization,
    // and holding an addressCache of data at the address.
    type XoState struct {
        context      *processor.Context
        addressCache map[string][]byte
    }

    // NewXoState constructs a new XoState struct.
    func NewXoState(context *processor.Context) *XoState {
        return &XoState{
            context:      context,
            addressCache: make(map[string][]byte),
        }
    }

    // GetGame returns a game by its name.
    func (self *XoState) GetGame(name string) (*Game, error) {
        games, err := self.loadGames(name)
        if err != nil {
            return nil, err
        }
        game, ok := games[name]
        if ok {
            return game, nil
        }
        return nil, nil
    }

    // SetGame sets a game to its name
    func (self *XoState) SetGame(name string, game *Game) error {
        games, err := self.loadGames(name)
        if err != nil {
            return err
        }

        games[name] = game

        return self.storeGames(name, games)
    }

    // DeleteGame deletes the game from state, handling
    // hash collisions.
    func (self *XoState) DeleteGame(name string) error {
        games, err := self.loadGames(name)
        if err != nil {
            return err
        }
        delete(games, name)
        if len(games) > 0 {
            return self.storeGames(name, games)
        } else {
            return self.deleteGames(name)
        }
    }

    func (self *XoState) loadGames(name string) (map[string]*Game, error) {
        address := makeAddress(name)

        data, ok := self.addressCache[address]
        if ok {
            if self.addressCache[address] != nil {
                return deserialize(data)
            }
            return make(map[string]*Game), nil

        }
        results, err := self.context.GetState([]string{address})
        if err != nil {
            return nil, err
        }
        if len(string(results[address])) > 0 {
            self.addressCache[address] = results[address]
            return deserialize(results[address])
        }
        self.addressCache[address] = nil
        games := make(map[string]*Game)
        return games, nil
    }

    func (self *XoState) storeGames(name string, games map[string]*Game) error {
        address := makeAddress(name)

        var names []string
        for name := range games {
            names = append(names, name)
        }
        sort.Strings(names)

        var g []*Game
        for _, name := range names {
            g = append(g, games[name])
        }

        data := serialize(g)

        self.addressCache[address] = data

        _, err := self.context.SetState(map[string][]byte{
            address: data,
        })
        return err
    }

    func (self *XoState) deleteGames(name string) error {
        address := makeAddress(name)

        _, err := self.context.DeleteState([]string{address})
        return err
    }

    func deserialize(data []byte) (map[string]*Game, error) {
        games := make(map[string]*Game)
        for _, str := range strings.Split(string(data), "|") {

            parts := strings.Split(string(str), ",")
            if len(parts) != 5 {
                return nil, &processor.InternalError{
                    Msg: fmt.Sprintf("Malformed game data: '%v'", string(data))}
            }

            game := &Game{
                Name:    parts[0],
                Board:   parts[1],
                State:   parts[2],
                Player1: parts[3],
                Player2: parts[4],
            }
            games[parts[0]] = game
        }

        return games, nil
    }

    func serialize(games []*Game) []byte {
        var buffer bytes.Buffer
        for i, game := range games {

            buffer.WriteString(game.Name)
            buffer.WriteString(",")
            buffer.WriteString(game.Board)
            buffer.WriteString(",")
            buffer.WriteString(game.State)
            buffer.WriteString(",")
            buffer.WriteString(game.Player1)
            buffer.WriteString(",")
            buffer.WriteString(game.Player2)
            if i+1 != len(games) {
                buffer.WriteString("|")
            }
        }
        return buffer.Bytes()
    }

    func hexdigest(str string) string {
        hash := sha512.New()
        hash.Write([]byte(str))
        hashBytes := hash.Sum(nil)
        return strings.ToLower(hex.EncodeToString(hashBytes))
    }

{% else %}

.. code-block:: python
    :caption: sawtooth_xo/processor/xo_state.py

    XO_NAMESPACE = hashlib.sha512('xo'.encode("utf-8")).hexdigest()[0:6]


    class Game(object):
        def __init__(self, name, board, state, player1, player2):
            self.name = name
            self.board = board
            self.state = state
            self.player1 = player1
            self.player2 = player2


    class XoState(object):

        TIMEOUT = 3

        def __init__(self, context):
            """Constructor.
            Args:
                context (sawtooth_sdk.processor.context.Context): Access to
                    validator state from within the transaction processor.
            """

            self._context = context
            self._address_cache = {}

        def delete_game(self, game_name):
            """Delete the Game named game_name from state.
            Args:
                game_name (str): The name.
            Raises:
                KeyError: The Game with game_name does not exist.
            """

            games = self._load_games(game_name=game_name)

            del games[game_name]
            if games:
                self._store_game(game_name, games=games)
            else:
                self._delete_game(game_name)

        def set_game(self, game_name, game):
            """Store the game in the validator state.
            Args:
                game_name (str): The name.
                game (Game): The information specifying the current game.
            """

            games = self._load_games(game_name=game_name)

            games[game_name] = game

            self._store_game(game_name, games=games)

        def get_game(self, game_name):
            """Get the game associated with game_name.
            Args:
                game_name (str): The name.
            Returns:
                (Game): All the information specifying a game.
            """

            return self._load_games(game_name=game_name).get(game_name)

        def _store_game(self, game_name, games):
            address = _make_xo_address(game_name)

            state_data = self._serialize(games)

            self._address_cache[address] = state_data

            self._context.set_state(
                {address: state_data},
                timeout=self.TIMEOUT)

        def _delete_game(self, game_name):
            address = _make_xo_address(game_name)

            self._context.delete_state(
                [address],
                timeout=self.TIMEOUT)

            self._address_cache[address] = None

        def _load_games(self, game_name):
            address = _make_xo_address(game_name)

            if address in self._address_cache:
                if self._address_cache[address]:
                    serialized_games = self._address_cache[address]
                    games = self._deserialize(serialized_games)
                else:
                    games = {}
            else:
                state_entries = self._context.get_state(
                    [address],
                    timeout=self.TIMEOUT)
                if state_entries:

                    self._address_cache[address] = state_entries[0].data

                    games = self._deserialize(data=state_entries[0].data)

                else:
                    self._address_cache[address] = None
                    games = {}

            return games

        def _deserialize(self, data):
            """Take bytes stored in state and deserialize them into Python
            Game objects.
            Args:
                data (bytes): The UTF-8 encoded string stored in state.
            Returns:
                (dict): game name (str) keys, Game values.
            """

            games = {}
            try:
                for game in data.decode().split("|"):
                    name, board, state, player1, player2 = game.split(",")

                    games[name] = Game(name, board, state, player1, player2)
            except ValueError:
                raise InternalError("Failed to deserialize game data")

            return games

        def _serialize(self, games):
            """Takes a dict of game objects and serializes them into bytes.
            Args:
                games (dict): game name (str) keys, Game values.
            Returns:
                (bytes): The UTF-8 encoded string stored in state.
            """

            game_strs = []
            for name, g in games.items():
                game_str = ",".join(
                    [name, g.board, g.state, g.player1, g.player2])
                game_strs.append(game_str)

            return "|".join(sorted(game_strs)).encode()


{% endif %}

Addressing
----------

By convention, we'll store game data at an address obtained from hashing the
game name prepended with some constant.

XO data is stored in state using addresses generated from the XO
family name and the name of the game being stored. In particular, an
XO address consists of the first 6 characters of the SHA-512 hash of
the UTF-8 encoding of the string "xo" (which is "5b7349") plus the
first 64 characters of the SHA-512 hash of the UTF-8 encoding of the
game name.

For example, the XO address for a game called "my-game" could be
generated as follows:

.. code-block:: pycon

    >>> x = hashlib.sha512('xo'.encode('utf-8')).hexdigest()[:6]
    >>> x
    '5b7349'
    >>> y = hashlib.sha512('my-game'.encode('utf-8')).hexdigest()[:64]
    >>> y
    '4d4cffe9cf3fb4e41def5114a323e292af9b0e07925cca6299d671ce7fc7ec37'
    >>> x+y
    '5b73494d4cffe9cf3fb4e41def5114a323e292af9b0e07925cca6299d671ce7fc7ec37'

Addressing is implemented as follows:

{% if language == 'JavaScript' %}

.. code-block:: javascript

    const _makeXoAddress = (x) => XO_NAMESPACE + _hash(x)

{% elif language == 'Go' %}

.. code-block:: go

    func makeAddress(name string) string {
	    return Namespace + hexdigest(name)[:64]
    }

{% else %}

.. code-block:: python

    def _make_xo_address(name):
    return XO_NAMESPACE + \
        hashlib.sha512(name.encode('utf-8')).hexdigest()[:64]


{% endif %}

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
