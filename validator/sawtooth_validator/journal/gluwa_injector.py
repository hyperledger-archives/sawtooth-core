import hashlib
import uuid
import logging

from sawtooth_validator.journal.batch_injector import BatchInjector
from sawtooth_validator.protobuf.transaction_pb2 import TransactionHeader
from sawtooth_validator.protobuf.transaction_pb2 import TransactionHeader
from sawtooth_validator.protobuf.transaction_pb2 import Transaction
from sawtooth_validator.protobuf.batch_pb2 import BatchHeader
from sawtooth_validator.protobuf.batch_pb2 import Batch

LOGGER = logging.getLogger(__name__)

class GluwaBatchInjector(BatchInjector):
    housekeeping_payload = b'\xa2avlHousekeepingbp1a0'

    def __init__(self, signer):
        self._signer = signer

    def block_start(self, _previous_block_id):
        pub_key = self._signer.get_public_key().as_hex()
        version = '1.7'
        ns = '8a1a04'
        payload = GluwaBatchInjector.housekeeping_payload
        tx_header = TransactionHeader(
            family_name='CREDITCOIN',
            family_version=version,
            inputs=[ns],
            outputs=[ns],
            nonce=str(uuid.uuid4()),
            batcher_public_key=pub_key,
            dependencies=[],
            signer_public_key=pub_key,
            payload_sha512=hashlib.sha512(payload).hexdigest()
        )
        tx_header_str = tx_header.SerializeToString()
        tx_header_signature = self._signer.sign(tx_header_str)
        tx = Transaction(
            payload=payload,
            header=tx_header_str,
            header_signature=tx_header_signature
        )
        txn_signatures = [tx.header_signature]
        batch_header = BatchHeader(
            signer_public_key=pub_key,
            transaction_ids=txn_signatures
        )
        batch_header_str = batch_header.SerializeToString()
        batch_header_signature = self._signer.sign(batch_header_str)
        batch = Batch(
            header=batch_header_str,
            transactions=[tx],
            header_signature=batch_header_signature
        )
        return [batch]
