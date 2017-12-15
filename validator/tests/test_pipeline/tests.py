import logging
import time
import unittest

from sawtooth_validator.concurrent.threadpool import \
    InstrumentedThreadPoolExecutor
from sawtooth_validator.concurrent.atomic import Counter
from sawtooth_validator.journal.block_pipeline import BlockPipeline
from sawtooth_validator.journal.block_pipeline import BlockPipelineStage
from sawtooth_validator.journal.block_pipeline import PipelineOutputEmpty
from sawtooth_validator.journal.block_pipeline import SimpleReceiverThread


LOGGER = logging.getLogger(__name__)


class MockStage(BlockPipelineStage):
    def __init__(self):
        self._executor = InstrumentedThreadPoolExecutor(1)
        self._receive_thread = None
        self._sender = None
        self._counter = Counter()

    def start(self, receiver, sender):
        if self._receive_thread is None:
            self._sender = sender
            self._receive_thread = SimpleReceiverThread(
                receiver=receiver,
                task=self.send_to_next,
                executor=self._executor)
            self._receive_thread.start()

    def stop(self):
        self._receive_thread.stop()
        self._sender = None
        self._receive_thread = None

    def has_block(self, block_id):
        return False

    def send_to_next(self, block):
        self._counter.inc()
        self._sender.send(block)

    def count(self):
        return self._counter.get()


class TestBlockPipeline(unittest.TestCase):
    def test_dummy(self):
        n_stages = 3
        n_items = 3

        stages = [
            MockStage() for _ in range(n_stages)
        ]

        pipeline = BlockPipeline()
        for stage in stages:
            pipeline.add_stage(stage)

        pipeline.start()
        for i in range(n_items):
            pipeline.submit(i)

        out = 0
        while out < n_items:
            try:
                item = pipeline.poll()
                self.assertEqual(item, out)
                out += 1
            except PipelineOutputEmpty:
                time.sleep(0.1)
        pipeline.stop()

        for stage in stages:
            self.assertEqual(stage.count(), n_items)
