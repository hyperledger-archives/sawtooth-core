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
