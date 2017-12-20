*******************************
Testing a Transaction Processor
*******************************

Say we've written a transaction processor -- how can it be tested? In this
section, we'll see how to test the XO transaction processor described in the
language-specific tutorials that show you how to write your own transaction
family (see the :doc:`/app_developers_guide`) against a mock validator.

Communication with the Validator
================================

First, let's look at what happens when the XO transaction 'create game000' is
processed. Communication between the validator and a transaction processor (TP)
takes place in six steps:

1) The validator needs to process a transaction, so it sends a transaction
process request to the TP containing the transaction information (in this case,
the command 'create' and the game name 'game000').

2) The TP needs to know whether a game already exists with the name 'game000',
so it sends a 'get' request back to the validator.

3) After querying state, the validator sends back the results to the TP (in
this case, we'll assume that there is no game called 'game000').

4) The TP now sends a message back to the validator requesting that it set
'game000' to an initialized game (with an empty board, etc).

5) The validator sends the address of the created game back to the TP.

6) The TP sends an 'OK' response to the validator, signaling that the
transaction was processed successfully.

This description suggests an outline for a test:

.. code-block:: python

    def test_create_game(self):
        self.validator_sends_tp_process_request(
            action='create',
            game='game000')

        get_message = self.validator_expects_get_request('game000')

        self.validator_responds_to_get_request(
            get_message,
            game='game000', board=None,
            state=None, player1=None, player2=None)

        set_message = self.validator_expects_set_request(
            game='game000', board='---------',
            state='P1-NEXT', player1='', player2='')

        self.validator_responds_to_set_request(set_message, 'game000')

        self.validator_expects_tp_response('OK')

Message Factory and Mock Validator
==================================

To implement these functions, we'll need a mock validator to send messages to
and from and a way manufacture the appropriate messages. How exactly the
messages are manufactured is not important here -- it's just a matter of
getting the relevant information into protobuf objects. This will be taken care
of for us by the *XoMessageFactory*
(``/project/sawtooth-core/sdk/examples/xo_python/sawtooth_xo/xo_message_factory.py``),
which itself relies on the more general *MessageFactory*
(``/project/sawtooth-core/sdk/python/sawtooth_processor_test/message_factory.py``).

To set up a mock validator, we can rely on *TransactionProcessorTestCase*
(``/project/sawtooth-core/sdk/python/sawtooth_processor_test/transaction_processor_test_case.py``).
This test class assumes that a transaction processor has been set up to connect
to a certain address. It creates a mock validator that binds to that address
(and closes the connection after all the tests have run):

.. code-block:: python

	class TransactionProcessorTestCase(unittest.TestCase):
	    @classmethod
	    def setUpClass(cls):
	        url = 'eth0:4004'

	        cls.validator = MockValidator()

	        cls.validator.listen(url)

	        if not cls.validator.register_processor():
	            raise Exception('Failed to register processor')

	        cls.factory = None

	    @classmethod
	    def tearDownClass(cls):
	        try:
	            cls.validator.close()
	        except AttributeError:
	            pass

Combining functions from the message factory and the test validator to create
our helper functions is straightforward:

.. code-block:: python

	class TestXo(TransactionProcessorTestCase):

	    @classmethod
	    def setUpClass(cls):
	        super().setUpClass()
	        cls.factory = XoMessageFactory()

	    def test_create_game(self):
	    	# ...

	    # helper functions

	    def validator_sends_tp_process_request(self, *args, **kwargs):
	        self.validator.send(
	            self.factory.create_tp_process_request(*args, **kwargs))

	    def validator_expects_get_request(self, key):
	        return self.validator.expect(
	            self.factory.create_get_request(key))

	    def validator_responds_to_get_request(self, message, *args, **kwargs):
	        self.validator.respond(
	            self.factory.create_get_response(*args, **kwargs),
	            message)

	    def validator_expects_set_request(self, *args, **kwargs):
	        return self.validator.expect(
	            self.factory.create_set_request(*args, **kwargs))

	    def validator_responds_to_set_request(self, message, *args, **kwargs):
	        self.validator.respond(
	            self.factory.create_set_response(*args, **kwargs),
	            message)

	    def validator_expects_tp_response(self, status):
	        return self.validator.expect(
	            self.factory.create_tp_response(status))

With this apparatus, we can easily create tests for other XO commands, like
taking a space:

.. code-block:: python

    def test_take_space(self):
        player1 = self.factory.get_public_key()

        self.validator_sends_tp_process_request(
            action='take',
            game='game000',
            space=3)

        get_message = self.validator_expects_get_request('game000')

        self.validator_responds_to_get_request(
            get_message,
            game='game000', board='---------',
            state='P1-NEXT', player1='', player2='')

        set_message = self.validator_expects_set_request(
            game='game000', board='--X------',
            state='P2-NEXT', player1=player1, player2='')

        self.validator_responds_to_set_request(set_message, 'game000')

        self.validator_expects_tp_response('OK')

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
