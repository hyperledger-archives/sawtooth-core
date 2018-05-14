import unittest
from unittest.mock import Mock

from sawtooth_validator.consensus import handlers
from sawtooth_validator.consensus.proxy import ConsensusProxy

from sawtooth_validator.journal.publisher import FinalizeBlockResult


class TestHandlers(unittest.TestCase):

    def setUp(self):
        self.mock_proxy = Mock()

    def test_consensus_register_handler(self):
        handler = handlers.ConsensusRegisterHandler()
        request_class = handler.request_class
        request = request_class()
        request.name = "test"
        request.version = "test"
        handler.handle(None, request.SerializeToString())

    def test_consensus_send_to_handler(self):
        handler = handlers.ConsensusSendToHandler(self.mock_proxy)
        request_class = handler.request_class
        request = request_class()
        request.peer_id = b"test"
        request.message.message_type = "test"
        request.message.content = b"test"
        request.message.name = "test"
        request.message.version = "test"
        handler.handle(None, request.SerializeToString())
        self.mock_proxy.send_to.assert_called_with(
            request.peer_id,
            request.message)

    def test_consensus_broadcast_handler(self):
        handler = handlers.ConsensusBroadcastHandler(self.mock_proxy)
        request_class = handler.request_class
        request = request_class()
        request.message.message_type = "test"
        request.message.content = b"test"
        request.message.name = "test"
        request.message.version = "test"
        handler.handle(None, request.SerializeToString())
        self.mock_proxy.broadcast.assert_called_with(
            request.message)

    def test_consensus_initialize_block_handler(self):
        handler = handlers.ConsensusInitializeBlockHandler(self.mock_proxy)
        request_class = handler.request_class
        request = request_class()
        request.previous_id = b"test"
        handler.handle(None, request.SerializeToString())
        self.mock_proxy.initialize_block.assert_called_with(
            request.previous_id)

    def test_consensus_finalize_block_handler(self):
        handler = handlers.ConsensusFinalizeBlockHandler(self.mock_proxy)
        request_class = handler.request_class
        request = request_class()
        request.data = b"test"
        handler.handle(None, request.SerializeToString())
        self.mock_proxy.finalize_block.assert_called_with(
            request.data)

    def test_consensus_cancel_block_handler(self):
        handler = handlers.ConsensusCancelBlockHandler(self.mock_proxy)
        request_class = handler.request_class
        request = request_class()
        handler.handle(None, request.SerializeToString())
        self.mock_proxy.cancel_block.assert_called_with()

    def test_consensus_check_block_handler(self):
        handler = handlers.ConsensusCheckBlockHandler(self.mock_proxy)
        request_class = handler.request_class
        request = request_class()
        request.block_ids.extend([b"test"])
        handler.handle(None, request.SerializeToString())
        self.mock_proxy.check_block.assert_called_with(
            request.block_ids)

    def test_consensus_commit_block_handler(self):
        handler = handlers.ConsensusCommitBlockHandler(self.mock_proxy)
        request_class = handler.request_class
        request = request_class()
        request.block_id = b"test"
        handler.handle(None, request.SerializeToString())
        self.mock_proxy.commit_block.assert_called_with(
            request.block_id)

    def test_consensus_ignore_block_handler(self):
        handler = handlers.ConsensusIgnoreBlockHandler(self.mock_proxy)
        request_class = handler.request_class
        request = request_class()
        request.block_id = b"test"
        handler.handle(None, request.SerializeToString())
        self.mock_proxy.ignore_block.assert_called_with(
            request.block_id)

    def test_consensus_fail_block_handler(self):
        handler = handlers.ConsensusFailBlockHandler(self.mock_proxy)
        request_class = handler.request_class
        request = request_class()
        request.block_id = b"test"
        handler.handle(None, request.SerializeToString())
        self.mock_proxy.fail_block.assert_called_with(
            request.block_id)

    def test_consensus_blocks_get_handler(self):
        handler = handlers.ConsensusBlocksGetHandler(self.mock_proxy)
        request_class = handler.request_class
        request = request_class()
        request.block_ids.extend([b"test"])
        handler.handle(None, request.SerializeToString())
        self.mock_proxy.blocks_get.assert_called_with(
            request.block_ids)

    def test_consensus_settings_get_handler(self):
        handler = handlers.ConsensusSettingsGetHandler(self.mock_proxy)
        request_class = handler.request_class
        request = request_class()
        request.block_id = b"test"
        request.keys.extend(["test"])
        handler.handle(None, request.SerializeToString())
        self.mock_proxy.settings_get.assert_called_with(
            request.block_id, request.keys)

    def test_consensus_state_get_handler(self):
        handler = handlers.ConsensusStateGetHandler(self.mock_proxy)
        request_class = handler.request_class
        request = request_class()
        request.block_id = b"test"
        request.addresses.extend(["test"])
        handler.handle(None, request.SerializeToString())
        self.mock_proxy.state_get.assert_called_with(
            request.block_id, request.addresses)


class TestProxy(unittest.TestCase):

    def setUp(self):
        self._mock_block_cache = {}
        self._mock_block_publisher = Mock()
        self._mock_chain_controller = Mock()
        self._proxy = ConsensusProxy(
            block_cache=self._mock_block_cache,
            chain_controller=self._mock_chain_controller,
            block_publisher=self._mock_block_publisher)

    def test_send_to(self):
        with self.assertRaises(NotImplementedError):
            self._proxy.send_to(None, None)

    def test_broadcast(self):
        with self.assertRaises(NotImplementedError):
            self._proxy.broadcast(None)

    # Using block publisher
    def test_initialize_block(self):
        self._proxy.initialize_block(None)
        self._mock_block_publisher.initialize_block.assert_called_with(
            self._mock_chain_controller.chain_head)

        self._mock_block_cache["34"] = "a block"
        self._proxy.initialize_block(previous_id=bytes([0x34]))
        self._mock_block_publisher\
            .initialize_block.assert_called_with("a block")

    def test_finalize_block(self):
        self._mock_block_publisher.finalize_block.return_value =\
            FinalizeBlockResult(
                block=None,
                remaining_batches=None,
                last_batch=None,
                injected_batches=None)

        data = bytes([0x56])
        self._proxy.finalize_block(data)
        self._mock_block_publisher.finalize_block.assert_called_with(
            consensus=data)
        self._mock_block_publisher.publish_block.assert_called_with(None, None)

    def test_cancel_block(self):
        self._proxy.cancel_block()
        self._mock_block_publisher.cancel_block.assert_called_with()

    # Using chain controller
    def test_check_block(self):
        with self.assertRaises(NotImplementedError):
            self._proxy.check_block(None)

    def test_commit_block(self):
        with self.assertRaises(NotImplementedError):
            self._proxy.commit_block(None)

    def test_ignore_block(self):
        with self.assertRaises(NotImplementedError):
            self._proxy.ignore_block(None)

    def test_fail_block(self):
        with self.assertRaises(NotImplementedError):
            self._proxy.fail_block(None)

    # Using blockstore and state database
    def test_blocks_get(self):
        with self.assertRaises(NotImplementedError):
            self._proxy.blocks_get(None)

    def test_settings_get(self):
        with self.assertRaises(NotImplementedError):
            self._proxy.settings_get(None, None)

    def test_state_get(self):
        with self.assertRaises(NotImplementedError):
            self._proxy.state_get(None, None)
