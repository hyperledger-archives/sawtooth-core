use sawtooth::{batch::Batch, block::Block};

use journal::publisher::{PublisherState, SyncPublisher};
use std::sync::RwLockWriteGuard;

/// Abstracts acquiring the lock used by the BlockPublisher without exposing access to the
/// publisher itself.
#[derive(Clone)]
pub struct ChainHeadLock {
    publisher: Box<dyn SyncPublisher>,
}

impl ChainHeadLock {
    pub fn new(publisher: Box<dyn SyncPublisher>) -> Self {
        ChainHeadLock { publisher }
    }

    pub fn acquire(&self) -> ChainHeadGuard {
        ChainHeadGuard {
            state: self
                .publisher
                .state()
                .write()
                .expect("Lock is not poisoned"),
            publisher: self.publisher.clone(),
        }
    }
}

/// RAII type that represents having acquired the lock used by the BlockPublisher
pub struct ChainHeadGuard<'a> {
    state: RwLockWriteGuard<'a, Box<dyn PublisherState>>,
    publisher: Box<dyn SyncPublisher>,
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
