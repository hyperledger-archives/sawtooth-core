import unittest
from unittest.mock import Mock

from sawtooth_validator.consensus import handlers
from sawtooth_validator.consensus.proxy import ConsensusProxy
from sawtooth_validator.consensus.proxy import UnknownBlock
from sawtooth_validator.consensus.registry import ConsensusRegistry, EngineInfo
from sawtooth_validator.protobuf.block_pb2 import BlockHeader


class FinalizeBlockResult:
    def __init__(self, block, remaining_batches, last_batch, injected_batches):
        self.block = block
        self.remaining_batches = remaining_batches
        self.last_batch = last_batch
        self.injected_batches = injected_batches


class TestHandlers(unittest.TestCase):

    def setUp(self):
        self.mock_proxy = Mock()
        self.mock_consensus_notifier = Mock()
        self.mock_consensus_registry = MockConsensusRegistry()

    def test_consensus_register_handler(self):
        handler = handlers.ConsensusRegisterHandler(self.mock_proxy)
        request_class = handler.request_class
        request = request_class()
        result = handler.handle('mock-id', request.SerializeToString())
        response = result.message_out
        self.assertEqual(response.status, handler.response_class.OK)
        self.mock_proxy.register.assert_called_with('', '', [], 'mock-id')

    def test_consensus_send_to_handler(self):
        handler = handlers.ConsensusSendToHandler(self.mock_proxy)
        request_class = handler.request_class
        request = request_class()
        request.receiver_id = b"test"
        request.message_type = "test"
        request.content = b"test"
        result = handler.handle(None, request.SerializeToString())
        response = result.message_out
        self.assertEqual(response.status, handler.response_class.OK)
        self.mock_proxy.send_to.assert_called_with(
            request.receiver_id,
            request.message_type,
            request.content,
            None)

    def test_consensus_broadcast_handler(self):
        handler = handlers.ConsensusBroadcastHandler(self.mock_proxy)
        request_class = handler.request_class
        request = request_class()
        request.message_type = "test"
        request.content = b"test"
        result = handler.handle(None, request.SerializeToString())
        response = result.message_out
        self.assertEqual(response.status, handler.response_class.OK)
        self.mock_proxy.broadcast.assert_called_with(
            request.message_type, request.content, None)

    def test_consensus_initialize_block_handler(self):
        handler = handlers.ConsensusInitializeBlockHandler(self.mock_proxy)
        request_class = handler.request_class
        request = request_class()
        request.previous_id = b"test"
        result = handler.handle('mock-id', request.SerializeToString())
        response = result.message_out
        self.assertEqual(response.status, handler.response_class.OK)
        self.mock_proxy.initialize_block.assert_called_with(
            request.previous_id)

    def test_consensus_summarize_block_handler(self):
        self.mock_proxy.summarize_block.return_value = b"1234"
        handler = handlers.ConsensusSummarizeBlockHandler(self.mock_proxy)
        request_class = handler.request_class
        request = request_class()
        result = handler.handle('mock-id', request.SerializeToString())
        response = result.message_out
        self.assertEqual(response.status, handler.response_class.OK)
        self.mock_proxy.summarize_block.assert_called_with()

    def test_consensus_finalize_block_handler(self):
        self.mock_proxy.finalize_block.return_value = b"1234"
        handler = handlers.ConsensusFinalizeBlockHandler(self.mock_proxy)
        request_class = handler.request_class
        request = request_class()
        request.data = b"test"
        result = handler.handle('mock-id', request.SerializeToString())
        response = result.message_out
        self.assertEqual(response.status, handler.response_class.OK)
        self.mock_proxy.finalize_block.assert_called_with(
            request.data)

    def test_consensus_cancel_block_handler(self):
        handler = handlers.ConsensusCancelBlockHandler(self.mock_proxy)
        request_class = handler.request_class
        request = request_class()
        result = handler.handle('mock-id', request.SerializeToString())
        response = result.message_out
        self.assertEqual(response.status, handler.response_class.OK)
        self.mock_proxy.cancel_block.assert_called_with()

    def test_consensus_check_blocks_handler(self):
        handler = handlers.ConsensusCheckBlocksHandler(self.mock_proxy)
        request_class = handler.request_class
        request = request_class()
        request.block_ids.extend([b"test"])
        result = handler.handle('mock-id', request.SerializeToString())
        response = result.message_out
        self.assertEqual(response.status, handler.response_class.OK)
        self.mock_proxy.check_blocks.assert_called_with(
            request.block_ids)

    def test_consensus_commit_block_handler(self):
        handler = handlers.ConsensusCommitBlockHandler(self.mock_proxy)
        request_class = handler.request_class
        request = request_class()
        request.block_id = b"test"
        result = handler.handle('mock-id', request.SerializeToString())
        response = result.message_out
        self.assertEqual(response.status, handler.response_class.OK)
        self.mock_proxy.commit_block.assert_called_with(
            request.block_id)

    def test_consensus_ignore_block_handler(self):
        handler = handlers.ConsensusIgnoreBlockHandler(self.mock_proxy)
        request_class = handler.request_class
        request = request_class()
        request.block_id = b"test"
        result = handler.handle('mock-id', request.SerializeToString())
        response = result.message_out
        self.assertEqual(response.status, handler.response_class.OK)
        self.mock_proxy.ignore_block.assert_called_with(
            request.block_id)

    def test_consensus_fail_block_handler(self):
        handler = handlers.ConsensusFailBlockHandler(self.mock_proxy)
        request_class = handler.request_class
        request = request_class()
        request.block_id = b"test"
        result = handler.handle('mock-id', request.SerializeToString())
        response = result.message_out
        self.assertEqual(response.status, handler.response_class.OK)
        self.mock_proxy.fail_block.assert_called_with(
            request.block_id)

    def test_consensus_blocks_get_handler(self):
        header = BlockHeader(previous_block_id='abcd')
        self.mock_proxy.blocks_get.return_value = [
            Mock(
                identifier='abcd',
                previous_block_id='abcd',
                header_signature='abcd',
                header=header.SerializeToString(),
                signer_public_key='abcd',
                block_num=1,
                consensus=b'consensus')]
        handler = handlers.ConsensusBlocksGetHandler(self.mock_proxy)
        request_class = handler.request_class
        request = request_class()
        request.block_ids.extend([b"test"])
        result = handler.handle('mock-id', request.SerializeToString())
        response = result.message_out
        self.assertEqual(response.status, handler.response_class.OK)
        self.mock_proxy.blocks_get.assert_called_with(
            request.block_ids)

    def test_consensus_chain_head_get_handler(self):
        header = BlockHeader(previous_block_id='abcd')
        self.mock_proxy.chain_head_get.return_value = Mock(
            identifier='abcd',
            previous_block_id='abcd',
            header_signature='abcd',
            header=header.SerializeToString(),
            signer_public_key='abcd',
            block_num=1,
            consensus=b'consensus')
        handler = handlers.ConsensusChainHeadGetHandler(self.mock_proxy)
        request_class = handler.request_class
        request = request_class()
        result = handler.handle('mock-id', request.SerializeToString())
        response = result.message_out
        self.assertEqual(response.status, handler.response_class.OK)
        self.mock_proxy.chain_head_get.assert_called_with()

    def test_consensus_settings_get_handler(self):
        self.mock_proxy.settings_get.return_value = [('key', 'value')]
        handler = handlers.ConsensusSettingsGetHandler(self.mock_proxy)
        request_class = handler.request_class
        request = request_class()
        request.block_id = b"test"
        request.keys.extend(["test"])
        result = handler.handle('mock-id', request.SerializeToString())
        response = result.message_out
        self.assertEqual(response.status, handler.response_class.OK)
        self.mock_proxy.settings_get.assert_called_with(
            request.block_id, request.keys)

    def test_consensus_state_get_handler(self):
        self.mock_proxy.state_get.return_value = [('address', b'data')]
        handler = handlers.ConsensusStateGetHandler(self.mock_proxy)
        request_class = handler.request_class
        request = request_class()
        request.block_id = b"test"
        request.addresses.extend(["test"])
        result = handler.handle('mock-id', request.SerializeToString())
        response = result.message_out
        self.assertEqual(response.status, handler.response_class.OK)
        self.mock_proxy.state_get.assert_called_with(
            request.block_id, request.addresses)


class TestProxy(unittest.TestCase):

    def setUp(self):
        self._mock_block_manager = MockBlockManager()
        self._mock_block_publisher = Mock()
        self._mock_chain_controller = Mock()
        self._mock_gossip = MockGossip()
        self._mock_identity_signer = MockIdentitySigner()
        self._mock_settings_view_factory = Mock()
        self._mock_state_view_factory = Mock()
        self._consensus_registry = MockConsensusRegistry()
        self._consensus_notifier = Mock()
        self._proxy = ConsensusProxy(
            block_manager=self._mock_block_manager,
            chain_controller=self._mock_chain_controller,
            block_publisher=self._mock_block_publisher,
            gossip=self._mock_gossip,
            identity_signer=self._mock_identity_signer,
            settings_view_factory=self._mock_settings_view_factory,
            state_view_factory=self._mock_state_view_factory,
            consensus_registry=self._consensus_registry,
            consensus_notifier=self._consensus_notifier)

    def test_send_to(self):
        self._proxy.send_to(
            peer_id=b'peer_id',
            content=b'message',
            message_type='message_type',
            connection_id=b'')

    def test_broadcast(self):
        self._proxy.broadcast(
            content=b'message',
            message_type='message_type',
            connection_id=b'')

    # Using block publisher
    def test_initialize_block(self):
        self._proxy.initialize_block(None)
        self._mock_block_publisher.initialize_block.assert_called_with(
            self._mock_chain_controller.chain_head)

        self._mock_block_manager["34"] = "a block"
        self._proxy.initialize_block(previous_id=bytes([0x34]))
        self._mock_block_publisher\
            .initialize_block.assert_called_with("a block")

    def test_summarize_block(self):
        self._mock_block_publisher.summarize_block.return_value =\
            b"summary"

        summary = self._proxy.summarize_block()
        self._mock_block_publisher.summarize_block.assert_called_with()
        self.assertEqual(summary, b"summary")

    def test_finalize_block(self):
        self._mock_block_publisher.finalize_block.return_value = "00"

        data = bytes([0x56])
        self._proxy.finalize_block(data)
        self._mock_block_publisher.finalize_block.assert_called_with(
            consensus=data)

    def test_cancel_block(self):
        self._proxy.cancel_block()
        self._mock_block_publisher.cancel_block.assert_called_with()

    # Using chain controller
    def test_check_blocks(self):
        block_ids = [bytes([0x56]), bytes([0x78])]
        self._mock_block_manager["56"] = "block0"
        self._mock_block_manager["78"] = "block1"
        self._proxy.check_blocks(block_ids)

        with self.assertRaises(UnknownBlock):
            self._proxy.check_blocks([bytes([0x00])])

    def test_commit_block(self):
        self._mock_block_manager["34"] = "a block"
        self._proxy.commit_block(block_id=bytes([0x34]))
        self._mock_chain_controller\
            .commit_block\
            .assert_called_with("a block")

    def test_ignore_block(self):
        self._mock_block_manager["34"] = "a block"
        self._proxy.ignore_block(block_id=bytes([0x34]))
        self._mock_chain_controller\
            .ignore_block\
            .assert_called_with("a block")

    def test_fail_block(self):
        self._mock_block_manager["34"] = "a block"
        self._proxy.fail_block(block_id=bytes([0x34]))
        self._mock_chain_controller\
            .fail_block\
            .assert_called_with("a block")

    # Using blockstore and state database
    def test_blocks_get(self):
        block_1 = Mock(
            identifier=b'id-1',
            previous_block_id=b'prev-1',
            header_signature=b'sign-1',
            block_num=1,
            consensus=b'consensus')

        self._mock_block_manager[b'block1'.hex()] = block_1

        block_2 = Mock(
            identifier=b'id-2',
            previous_block_id=b'prev-2',
            header_signature=b'sign-2',
            block_num=2,
            consensus=b'consensus')

        self._mock_block_manager[b'block2'.hex()] = block_2

        proxy_block_1, proxy_block_2 = self._proxy.blocks_get([
            b'block1',
            b'block2'])

        self.assertEqual(
            block_1,
            proxy_block_1)

        self.assertEqual(
            block_2,
            proxy_block_2)

    def test_chain_head_get(self):
        chain_head = Mock(
            identifier=b'id-2',
            previous_block_id=b'prev-2',
            header_signature=b'sign-2',
            block_num=2,
            consensus=b'consensus')

        self._mock_chain_controller.chain_head = chain_head

        self.assertEqual(
            self._proxy.chain_head_get(),
            chain_head)

    @unittest.skip("Test will have to be rethought due to removal of "
                   "blockwrapper from proxy")
    def test_settings_get(self):
        self._mock_block_manager[b'block'.hex()] = MockBlock()

        self.assertEqual(
            self._proxy.settings_get(b'block', ['key1', 'key2']),
            [
                ('key1', 'mock-key1'),
                ('key2', 'mock-key2'),
            ])

    @unittest.skip("Test will have to be rethought due to removal of "
                   "blockwrapper from proxy")
    def test_state_get(self):
        self._mock_block_manager[b'block'.hex()] = MockBlock()

        address_1 = '1' * 70
        address_2 = '2' * 70

        self.assertEqual(
            self._proxy.state_get(b'block', [address_1, address_2]),
            [
                (address_1, 'mock-{}'.format(address_1).encode()),
                (address_2, 'mock-{}'.format(address_2).encode()),
            ])


class TestRegistry(unittest.TestCase):

    def test_consensus_registry(self):
        registry = ConsensusRegistry()

        assert not registry.has_active_engine()

        # Test basic registration/activation
        registry.register_engine(
            'id0', 'name1', 'version1', [('name-a', 'version-a')])
        registry.activate_engine('name1', 'version1')
        assert registry.is_active_engine_id('id0')
        assert registry.is_active_engine_name_version('name1', 'version1')

        # Test deactivation
        registry.deactivate_current_engine()
        assert not registry.has_active_engine()

        # Test activating by additional protocol
        registry.activate_engine('name-a', 'version-a')
        assert registry.is_active_engine_name_version('name1', 'version1')

        # Test re-registration of existing engine
        registry.register_engine(
            'id1', 'name1', 'version1', [('name-a', 'version-a')])
        assert not registry.has_active_engine()
        registry.activate_engine('name1', 'version1')
        assert registry.is_active_engine_name_version('name1', 'version1')

        # Test upgrading engine
        registry.register_engine(
            'id2', 'name2', 'version2',
            [('name1', 'version1'), ('name-a', 'version-a')])
        assert not registry.has_active_engine()
        registry.activate_engine('name2', 'version2')
        assert registry.is_active_engine_name_version('name2', 'version2')

        # Test two engines that support the same protocol can be registered;
        # first engine to register should be activated
        registry.register_engine(
            'id3', 'name3', 'version3', [('name-a', 'version-a')])
        assert registry.is_active_engine_name_version('name2', 'version2')
        registry.deactivate_current_engine()
        registry.activate_engine('name-a', 'version-a')
        assert registry.is_active_engine_name_version('name2', 'version2')


class MockBlock:
    def get_state_view(self, state_view_factory):
        return MockStateView()

    def get_settings_view(self, settings_view_factory):
        return MockSettingsView()


class MockBlockManager:

    def __init__(self):
        self._cache = {}

    def put(self, blocks):
        for block in blocks:
            self._cache[block.header_signature] = block

    def get(self, block_ids):
        return iter([self._cache[block_id] for block_id in block_ids])

    def __contains__(self, item):
        return item in self._cache

    def __setitem__(self, key, value):
        self._cache[key] = value


class MockConsensusRegistry(Mock):
    def get_active_engine_info(self):
        return EngineInfo('mock-id', 'mock-name', 'mock-version',
                          [('alt-protocol-name', 'alt-protocol-version')])

    def is_active_engine_id(self, engine_id):
        return True


class MockGossip(Mock):
    def peer_to_public_key(self, peer):
        return 'mock-{}'.format(peer)

    def get_peers(self):
        return []


class MockPubKey:
    def as_bytes(self):
        return 'mock-pubkey-as-bytes'.encode()


class MockIdentitySigner(Mock):
    def get_public_key(self):
        return MockPubKey()

    def sign(self, message):
        return 'abcd'


class MockStateView:
    def get(self, address):
        return 'mock-{}'.format(address).encode()


class MockSettingsView:
    def get_setting(self, key):
        return 'mock-{}'.format(key)
