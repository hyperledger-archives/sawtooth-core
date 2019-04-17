# Copyright 2018 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ------------------------------------------------------------------------------

from sawtooth_validator.consensus import handlers


def add(
        dispatcher,
        thread_pool,
        consensus_proxy,
        consensus_notifier
):

    handler = handlers.ConsensusRegisterHandler(consensus_proxy)
    dispatcher.add_handler(handler.request_type, handler, thread_pool)

    handler = handlers.ConsensusRegisterActivateHandler(consensus_proxy)
    dispatcher.add_handler(handler.request_type, handler, thread_pool)

    handler = handlers.ConsensusSendToHandler(consensus_proxy)
    dispatcher.add_handler(handler.request_type, handler, thread_pool)

    handler = handlers.ConsensusBroadcastHandler(consensus_proxy)
    dispatcher.add_handler(handler.request_type, handler, thread_pool)

    handler = handlers.ConsensusInitializeBlockHandler(consensus_proxy)
    dispatcher.add_handler(handler.request_type, handler, thread_pool)

    handler = handlers.ConsensusSummarizeBlockHandler(consensus_proxy)
    dispatcher.add_handler(handler.request_type, handler, thread_pool)

    handler = handlers.ConsensusFinalizeBlockHandler(consensus_proxy)
    dispatcher.add_handler(handler.request_type, handler, thread_pool)

    handler = handlers.ConsensusCancelBlockHandler(consensus_proxy)
    dispatcher.add_handler(handler.request_type, handler, thread_pool)

    handler = handlers.ConsensusCheckBlocksHandler(consensus_proxy)
    dispatcher.add_handler(handler.request_type, handler, thread_pool)

    handler = handlers.ConsensusCheckBlocksNotifier(
        consensus_proxy, consensus_notifier)
    dispatcher.add_handler(handler.request_type, handler, thread_pool)

    handler = handlers.ConsensusCommitBlockHandler(consensus_proxy)
    dispatcher.add_handler(handler.request_type, handler, thread_pool)

    handler = handlers.ConsensusIgnoreBlockHandler(consensus_proxy)
    dispatcher.add_handler(handler.request_type, handler, thread_pool)

    handler = handlers.ConsensusFailBlockHandler(consensus_proxy)
    dispatcher.add_handler(handler.request_type, handler, thread_pool)

    handler = handlers.ConsensusBlocksGetHandler(consensus_proxy)
    dispatcher.add_handler(handler.request_type, handler, thread_pool)

    handler = handlers.ConsensusChainHeadGetHandler(consensus_proxy)
    dispatcher.add_handler(handler.request_type, handler, thread_pool)

    handler = handlers.ConsensusSettingsGetHandler(consensus_proxy)
    dispatcher.add_handler(handler.request_type, handler, thread_pool)

    handler = handlers.ConsensusStateGetHandler(consensus_proxy)
    dispatcher.add_handler(handler.request_type, handler, thread_pool)
