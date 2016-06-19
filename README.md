
Sawtooth Lake Arcade
====================

This repository contains example code, in the form of games, which demonstrate
key concepts of Sawtooth Lake.

The documentation for Sawtooth Lake is available at:

  http://intelledger.github.io/

Sawtooth Tac Toe
----------------

Sawtooth Tac Toe contains two components:

  - A transaction family, sawtooth\_xo, which implements game rules
  - A client, xo, and client-side library code

The primary purpose of this game is to provide a simple transaction family
implementation which demonstrates the APIs available in sawtooth-core.

To use the sawtooth\_xo transaction family, it must be added to the list of
transaction families in txnvalidator.js:

```javascript
     "TransactionFamilies" : [
        "sawtooth_xo"
     ],
```

txnvalidator must be able to find the sawtooth_xo transaction family
implementation, which can be done by adding this repository directory to the
PYTHONPATH environment variable.

The xo client has several subcommands (create, init, list, show, take)
which will be covered briefly here.

To start using xo, first run 'xo init' with the option --username
parameter:

```
$ ./bin/xo init --username=bob
set username: bob
writing file: /home/vagrant/.sawtooth/keys/bob.wif
writing file: /home/vagrant/.sawtooth/keys/bob.addr
```

The init subcommand can be re-used to switch to a new user (for example,
if you want to switch between two players locally).  A key will only be
generated if it does not already exist.

The default URL is 'http://localhost:8800'.  If you are connecting to
a different validator, edit $HOME/.sawtooth/xo.cfg (which was created
by the init command).

To create a game:

```
$ ./bin/xo create game000
```

To view the list of current games:

```
$ ./bin/xo list
GAME            PLAYER 1        PLAYER 2        BOARD     STATE
game000         1AmEGiWz3gdbcY2 1PpMLcLt4Wgf1uU XO------- P1-NEXT
```

Note that it may take time for a new game to appear in the list, since the
transaction to create a new game is asynchronous.  This applies to both
create and take.

To 'take a space' in game000:

```
$ ./bin/xo take game000 1
```

This takes space 1 in game 000.  Spaces are numbered like:

```
 1 | 2 | 3
---|---|---
 4 | 5 | 6
---|---|---
 7 | 8 | 9
```

You can use the show subcommand to view the board:

```
$ ./bin/xo show game000
GAME:     : game000
PLAYER 1  : 16hfGNPcyrQ3UqAC1jQS6wthGEeryGxHaR
PLAYER 2  :
STATE     : P2-NEXT

  X |   |
 ---|---|---
    |   |
 ---|---|---
    |   |

```

You can use the help option to get usage for xo; for example, "xo create -h".

You can turn up the verbosity of the command (which enables logging output
to the console) by adding -v or -vv.  -v enables INFO-level messages and
-vv enables DEBUG-level messages.

Sawtooth Ethereum Guess
-----------------------

seg is a game about guessing the balances of Ethereum addresses.  While it
isn't really fun... it does show how to integrate an Ethereum client into
a transaction family (thus using Ethereum as a source of record for some
data).

Sawtooth Rock Paper Scissors
----------------------------

rps is a very basic multiplayer rock paper scissors implementation. All
players will be playing against the creator of the game.

Currently anybody can join the game until all player slots are filled.

Game state is stored plainly into the blockchain. This means that everybody
can see the hands that are played even before the round as ended.

Thoughts for improvements; multiple rounds, keep hands secret until every
player has send in his hand, play against the computer, create game for
specific players only.
