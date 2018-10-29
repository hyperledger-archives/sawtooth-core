/*
 * Copyright 2018 Intel Corporation
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * ------------------------------------------------------------------------------
 */

use batch::Batch;
use block::Block;
use journal::publisher::{BlockPublisherState, SyncBlockPublisher};
use std::sync::RwLockWriteGuard;

/// Abstracts acquiring the lock used by the BlockPublisher without exposing access to the
/// publisher itself.
#[derive(Clone)]
pub struct ChainHeadLock {
    publisher: SyncBlockPublisher,
}

impl ChainHeadLock {
    pub fn new(publisher: SyncBlockPublisher) -> Self {
        ChainHeadLock { publisher }
    }

    pub fn acquire(&self) -> ChainHeadGuard {
        ChainHeadGuard {
            state: self.publisher.state.write().expect("Lock is not poisoned"),
            publisher: self.publisher.clone(),
        }
    }
}

/// RAII type that represents having acquired the lock used by the BlockPublisher
pub struct ChainHeadGuard<'a> {
    state: RwLockWriteGuard<'a, BlockPublisherState>,
    publisher: SyncBlockPublisher,
}

impl<'a> ChainHeadGuard<'a> {
    pub fn notify_on_chain_updated(
        &mut self,
        chain_head: Block,
        committed_batches: Vec<Batch>,
        uncommitted_batches: Vec<Batch>,
    ) {
        self.publisher.on_chain_updated(
            &mut self.state,
            chain_head,
            committed_batches,
            uncommitted_batches,
        )
    }
}
