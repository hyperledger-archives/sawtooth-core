from sawtooth_validator.journal.batch_injector import BatchInjector
from sawtooth_validator.protobuf.transaction_pb2 import TransactionHeader
from sawtooth_validator.protobuf.transaction_pb2 import Transaction
from sawtooth_validator.protobuf.batch_pb2 import BatchHeader
from sawtooth_validator.protobuf.batch_pb2 import Batch


from sawtooth_validator.protobuf.obligatory_payment_pb2 import (
    ObligatoryPaymentPayload,
    ObligatoryPaymentMethod
)

import hashlib

FAMILY_NAME = 'obligatory_payment'
FAMILY_VERSIONS = ['0.1']


def hash512(data):
    return hashlib.sha512(data.encode('utf-8')
                          if isinstance(data, str) else data).hexdigest()


prefix = hash512(FAMILY_NAME)[:6]


def make_address(appendix):
    address = prefix + appendix
    return address


def make_address_from_data(data):
        appendix = hash512(data)[:64]
        return make_address(appendix)


class ObligatoryPaymentInjector(BatchInjector):
    """Inject ObligatoryPayment transaction at the beginning of blocks."""

    def __init__(self, state_view_factory, signer):
        self._state_view_factory = state_view_factory
        self._signer = signer

    def create_batch(self):
        payload = ObligatoryPaymentPayload().SerializeToString()
        public_key = self._signer.get_public_key().as_hex()

        block_signer_address = make_address_from_data(data=public_key)

        INPUTS = OUTPUTS = [
            block_signer_address
        ]
        #TODO: also for inputs and outputs need addresses of other masternodes in committee.

        header = TransactionHeader(
            signer_public_key=public_key,
            family_name=FAMILY_NAME,
            family_version=FAMILY_VERSIONS[0],
            inputs=INPUTS,
            outputs=OUTPUTS,
            dependencies=[],
            payload_sha512=hash512(payload).hexdigest(),
            batcher_public_key=public_key,
        ).SerializeToString()

        transaction_signature = self._signer.sign(header)

        transaction = Transaction(
            header=header,
            payload=payload,
            header_signature=transaction_signature,
        )

        header = BatchHeader(
            signer_public_key=public_key,
            transaction_ids=[transaction_signature],
        ).SerializeToString()

        batch_signature = self._signer.sign(header)

        return Batch(
            header=header,
            transactions=[transaction],
            header_signature=batch_signature,
        )

    def block_start(self, previous_block):
        """Returns an ordered list of batches to inject at the beginning of the
        block. Can also return None if no batches should be injected.
        Args:
            previous_block (Block): The previous block.
        Returns:
            A list of batches to inject.
        """

        return [self.create_batch()]

    def before_batch(self, previous_block, batch):
        pass

    def after_batch(self, previous_block, batch):
        pass

    def block_end(self, previous_block, batches):
        pass
