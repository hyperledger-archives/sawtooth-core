import unittest
from unittest.mock import Mock

from sawtooth_validator.consensus import handlers


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
