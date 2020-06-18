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

#![allow(unknown_lints)]

use std::collections::HashMap;
use std::io;
use std::marker::Send;
use std::marker::Sync;
use std::sync::atomic::AtomicBool;
use std::sync::atomic::Ordering;
use std::sync::mpsc;
use std::sync::mpsc::channel;
use std::sync::mpsc::Receiver;
use std::sync::mpsc::RecvError;
use std::sync::mpsc::Sender;
use std::sync::Arc;
use std::sync::Mutex;
use std::sync::RwLock;
use std::thread;
use std::time::Duration;

use protobuf;

use batch::Batch;
use block::Block;
use consensus::notifier::ConsensusNotifier;
use consensus::registry::ConsensusRegistry;
use execution::execution_platform::ExecutionPlatform;
use gossip::permission_verifier::PermissionVerifier;
use journal;
use journal::block_manager::{BlockManager, BlockManagerError, BlockRef};
use journal::block_validator::{
    BlockValidationResult, BlockValidationResultStore, BlockValidator, ValidationError,
};
use journal::block_wrapper::BlockStatus;
use journal::chain_head_lock::ChainHeadLock;
use journal::chain_id_manager::ChainIdManager;
use journal::fork_cache::ForkCache;
use metrics;
use state::state_pruning_manager::StatePruningManager;
use state::state_view_factory::StateViewFactory;

use proto::transaction_receipt::TransactionReceipt;
use scheduler::TxnExecutionResult;

const RECV_TIMEOUT_MILLIS: u64 = 100;

pub const COMMIT_STORE: &str = "commit_store";

lazy_static! {
    static ref COLLECTOR: metrics::MetricsCollectorHandle =
        metrics::get_collector("sawtooth_validator.chain");
}

#[derive(Debug)]
pub enum ChainControllerError {
    QueueRecvError(RecvError),
    ChainIdError(io::Error),
    ChainUpdateError(String),
    ChainReadError(ChainReadError),
    ForkResolutionError(String),
    BlockValidationError(ValidationError),
    BrokenQueue,
    ConsensusError(String),
    UnknownBlock(String),
}

impl From<RecvError> for ChainControllerError {
    fn from(err: RecvError) -> Self {
        ChainControllerError::QueueRecvError(err)
    }
}

impl From<io::Error> for ChainControllerError {
    fn from(err: io::Error) -> Self {
        ChainControllerError::ChainIdError(err)
    }
}

impl From<ValidationError> for ChainControllerError {
    fn from(err: ValidationError) -> Self {
        ChainControllerError::BlockValidationError(err)
    }
}

impl From<ChainReadError> for ChainControllerError {
    fn from(err: ChainReadError) -> Self {
        ChainControllerError::ChainReadError(err)
    }
}

impl From<ForkResolutionError> for ChainControllerError {
    fn from(err: ForkResolutionError) -> Self {
        ChainControllerError::ForkResolutionError(err.0)
    }
}

impl From<BlockManagerError> for ChainControllerError {
    fn from(err: BlockManagerError) -> Self {
        ChainControllerError::ChainUpdateError(format!("{:?}", err))
    }
}

pub trait ChainObserver: Send + Sync {
    fn chain_update(&mut self, block: &Block, receipts: &[TransactionReceipt]);
}

#[derive(Debug)]
pub enum ChainReadError {
    GeneralReadError(String),
}

pub trait ChainReader: Send + Sync {
    fn chain_head(&self) -> Result<Option<Block>, ChainReadError>;
    fn count_committed_transactions(&self) -> Result<usize, ChainReadError>;
    fn get_block_by_block_num(&self, block_num: u64) -> Result<Option<Block>, ChainReadError>;
    fn get_block_by_block_id(&self, block_id: &str) -> Result<Option<Block>, ChainReadError>;
}

/// Holds the results of Block Validation.
struct ForkResolutionResult<'a> {
    pub block: &'a Block,
    pub chain_head: Option<&'a Block>,

    pub new_chain: Vec<Block>,
    pub current_chain: Vec<Block>,

    pub committed_batches: Vec<Batch>,
    pub uncommitted_batches: Vec<Batch>,

    pub transaction_count: usize,
}

/// Indication that an error occured during fork resolution.
#[derive(Debug)]
struct ForkResolutionError(String);

struct ChainControllerState {
    block_manager: BlockManager,
    block_references: HashMap<String, BlockRef>,
    chain_reader: Box<ChainReader>,
    chain_head: Option<BlockRef>,
    chain_id_manager: ChainIdManager,
    observers: Vec<Box<ChainObserver>>,
    state_pruning_manager: StatePruningManager,
    fork_cache: ForkCache,
}

impl ChainControllerState {
    fn build_fork<'a>(
        &mut self,
        block: &'a Block,
        chain_head: &'a Block,
    ) -> Result<ForkResolutionResult<'a>, ChainControllerError> {
        let new_block = block.clone();

        let new_chain = self
            .block_manager
            .branch_diff(&new_block.header_signature, &chain_head.header_signature)?
            .collect::<Vec<Block>>();
        let current_chain = self
            .block_manager
            .branch_diff(&chain_head.header_signature, &new_block.header_signature)?
            .collect::<Vec<Block>>();

        let committed_batches: Vec<Batch> = new_chain.iter().fold(vec![], |mut batches, block| {
            batches.append(&mut block.batches.clone());
            batches
        });
        let uncommitted_batches: Vec<Batch> =
            current_chain.iter().fold(vec![], |mut batches, block| {
                batches.append(&mut block.batches.clone());
                batches
            });

        let transaction_count = committed_batches.iter().fold(0, |mut txn_count, batch| {
            txn_count += batch.transactions.len();
            txn_count
        });

        let result = ForkResolutionResult {
            block,
            chain_head: Some(chain_head),
            new_chain,
            current_chain,
            committed_batches,
            uncommitted_batches,
            transaction_count,
        };

        info!(
            "Building fork resolution for chain head '{}' against new block '{}'",
            &chain_head, &new_block
        );
        if let Some(prior_heads_successor) = result.new_chain.get(0) {
            if prior_heads_successor.previous_block_id != chain_head.header_signature {
                let mut moved_to_fork_count =
                    COLLECTOR.counter("ChainController.chain_head_moved_to_fork_count", None, None);
                moved_to_fork_count.inc();
            }
        }

        Ok(result)
    }

    fn check_chain_head_updated(
        &self,
        expected_chain_head: &Block,
        block: &Block,
    ) -> Result<bool, ChainControllerError> {
        let actual_chain_head = self.chain_reader.chain_head()?;

        let chain_head_updated = actual_chain_head.as_ref().map(|actual_chain_head| {
            actual_chain_head.header_signature != expected_chain_head.header_signature
        });

        if chain_head_updated.unwrap_or(false) {
            warn!(
                "Chain head updated from {} to {} while resolving \
                 fork for block {}. Reprocessing resolution.",
                expected_chain_head,
                actual_chain_head.as_ref().unwrap(),
                block
            );
            return Ok(true);
        }

        Ok(false)
    }
}

#[derive(Clone)]
pub struct ChainController<TEP: ExecutionPlatform + Clone, PV: PermissionVerifier + Clone> {
    state: Arc<RwLock<ChainControllerState>>,
    stop_handle: Arc<Mutex<Option<ChainThreadStopHandle>>>,

    consensus_notifier: Arc<ConsensusNotifier>,
    consensus_registry: Arc<ConsensusRegistry>,
    state_view_factory: StateViewFactory,
    block_validator: BlockValidator<TEP, PV>,
    block_validation_results: BlockValidationResultStore,

    // Queues
    block_queue_sender: Option<Sender<String>>,
    commit_queue_sender: Option<Sender<Block>>,
    validation_result_sender: Option<Sender<BlockValidationResult>>,

    state_pruning_block_depth: u32,
    chain_head_lock: ChainHeadLock,
}

impl<TEP: ExecutionPlatform + Clone + 'static, PV: PermissionVerifier + Clone + 'static>
    ChainController<TEP, PV>
{
    #![allow(clippy::too_many_arguments)]
    pub fn new(
        block_manager: BlockManager,
        block_validator: BlockValidator<TEP, PV>,
        chain_reader: Box<ChainReader>,
        chain_head_lock: ChainHeadLock,
        block_validation_results: BlockValidationResultStore,
        consensus_notifier: Box<ConsensusNotifier>,
        consensus_registry: Box<ConsensusRegistry>,
        state_view_factory: StateViewFactory,
        data_dir: String,
        state_pruning_block_depth: u32,
        observers: Vec<Box<ChainObserver>>,
        state_pruning_manager: StatePruningManager,
        fork_cache_keep_time: Duration,
    ) -> Self {
        let mut chain_controller = ChainController {
            state: Arc::new(RwLock::new(ChainControllerState {
                block_manager,
                block_references: HashMap::new(),
                chain_reader,
                chain_id_manager: ChainIdManager::new(data_dir),
                observers,
                chain_head: None,
                state_pruning_manager,
                fork_cache: ForkCache::new(fork_cache_keep_time),
            })),
            block_validator,
            block_validation_results,
            stop_handle: Arc::new(Mutex::new(None)),
            block_queue_sender: None,
            commit_queue_sender: None,
            validation_result_sender: None,
            state_pruning_block_depth,
            chain_head_lock,
            consensus_notifier: Arc::from(consensus_notifier),
            consensus_registry: Arc::from(consensus_registry),
            state_view_factory,
        };

        chain_controller.initialize_chain_head();

        chain_controller
    }

    pub fn chain_head(&self) -> Option<Block> {
        let state = self
            .state
            .read()
            .expect("No lock holder should have poisoned the lock");

        if let Some(head) = &state.chain_head {
            self.get_block(head.block_id())
        } else {
            None
        }
    }

    pub fn block_validation_result(&self, block_id: &str) -> Option<BlockValidationResult> {
        self.block_validation_results.get(block_id).or_else(|| {
            if self
                .state
                .read()
                .expect("Unable to acquire read lock, due to poisoning")
                .chain_reader
                .get_block_by_block_id(block_id)
                .expect("ChainReader errored reading from the database")
                .is_some()
            {
                let result = BlockValidationResult {
                    block_id: block_id.into(),
                    execution_results: vec![],
                    num_transactions: 0,
                    status: BlockStatus::Valid,
                };
                return Some(result);
            }
            None
        })
    }

    /// This is used by a non-genesis journal when it has received the
    /// genesis block from the genesis validator
    fn set_genesis(
        &self,
        state: &mut ChainControllerState,
        lock: &ChainHeadLock,
        block: &Block,
    ) -> Result<(), ChainControllerError> {
        if block.previous_block_id == journal::NULL_BLOCK_IDENTIFIER {
            let chain_id = state.chain_id_manager.get_block_chain_id()?;
            if chain_id
                .as_ref()
                .map(|block_id| block_id != &block.header_signature)
                .unwrap_or(false)
            {
                warn!(
                    "Block id does not match block chain id {}. Ignoring initial chain head: {}",
                    chain_id.unwrap(),
                    block.header_signature
                );
            } else {
                self.block_validator.validate_block(&block)?;

                if chain_id.is_none() {
                    state
                        .chain_id_manager
                        .save_block_chain_id(&block.header_signature)?;
                }

                state
                    .block_manager
                    .persist(&block.header_signature, COMMIT_STORE)?;

                // Create Ref-C: External reference for the chain head will be held until it is
                // superceded by a new chain head.
                state.chain_head = Some(
                    state
                        .block_manager
                        .ref_block(block.header_signature.as_str())?,
                );

                match self.block_validation_results.get(&block.header_signature) {
                    Some(validation_results) => {
                        let receipts: Vec<TransactionReceipt> = validation_results
                            .execution_results
                            .iter()
                            .map(TransactionReceipt::from)
                            .collect();
                        for observer in &mut state.observers {
                            observer.chain_update(&block, receipts.as_slice());
                        }
                    }
                    None => {
                        error!(
                            "While committing {}, found block missing execution results",
                            &block,
                        );
                    }
                }

                let mut guard = lock.acquire();
                guard.notify_on_chain_updated(block.clone(), vec![], vec![]);
            }
        }

        Ok(())
    }

    pub fn on_block_received(&mut self, block_id: &str) -> Result<(), ChainControllerError> {
        // Only need a read lock to check duplicates, but need to upgrade to write lock for
        // updating chain head.
        {
            let mut state = self
                .state
                .write()
                .expect("No lock holder should have poisoned the lock");

            if state.chain_head.is_none() {
                if let Some(Some(block)) = state.block_manager.get(&[&block_id]).nth(0) {
                    if let Err(err) = self.set_genesis(&mut state, &self.chain_head_lock, &block) {
                        warn!(
                            "Unable to set chain head; genesis block {} is not valid: {:?}",
                            &block.header_signature, err
                        );
                    }
                } else {
                    warn!("Received block not in block manager");
                }
                return Ok(());
            }
        }

        let block = {
            let mut state = self
                .state
                .write()
                .expect("No lock holder should have poisoned the lock");

            if let Some(Some(block)) = state.block_manager.get(&[&block_id]).nth(0) {
                // Create Ref-C: Hold this reference until consensus renders a {commit, ignore, or
                // fail} opinion on the block.
                match state.block_manager.ref_block(&block_id) {
                    Ok(block_ref) => {
                        state
                            .block_references
                            .insert(block_ref.block_id().to_owned(), block_ref);
                        self.consensus_notifier.notify_block_new(&block);
                        Some(block)
                    }
                    Err(err) => {
                        error!(
                            "Unable to ref block {} received from completer; ignoring: {:?}",
                            &block_id, err
                        );
                        None
                    }
                }
            } else {
                warn!(
                    "Received block id for block not in block manager: {}",
                    block_id
                );
                None
            }
        };

        if let Some(block) = block {
            let mut state = self
                .state
                .write()
                .expect("No lock holder should have poisoned the lock");

            // Transfer Ref-B: Implicitly transfer ownership of the external reference placed on
            // this block by the completer. The ForkCache is now responsible for unrefing the block
            // when it expires. This happens when either 1) the block is replaced in the cache by
            // another block which extends it, at which point this block will have an int. ref.
            // count of at least 1, or 2) the fork becomes inactive the block is purged, at which
            // point the block may be dropped if no other ext. ref's exist.
            if let Some(previous_block_id) = state
                .fork_cache
                .insert(&block_id, Some(&block.previous_block_id))
            {
                // Drop Ref-B: This fork was extended and so this block has an int. ref. count of
                // at least one, so we can drop the ext. ref. placed on the block to keep the fork
                // around.
                match state.block_manager.unref_block(&previous_block_id) {
                    Ok(true) => {
                        panic!(
                            "Block {:?} was unref'ed because it was the head of a fork that was
                            just extended. The unref caused the block to drop, but it should have
                            had an internal reference count of at least 1.",
                            previous_block_id,
                        );
                    }
                    Ok(false) => (),
                    Err(err) => error!(
                        "Failed to unref expired block {}: {:?}",
                        previous_block_id, err
                    ),
                }
            }

            for block_id in state.fork_cache.purge() {
                // Drop Ref-B: The fork is no longer active, and we have to drop the ext. ref.
                // placed on the block to keep the fork around.
                if let Err(err) = state.block_manager.unref_block(&block_id) {
                    error!("Failed to unref expired block {}: {:?}", block_id, err);
                }
            }
        }

        Ok(())
    }

    pub fn validate_block(&self, block: &Block) {
        // If there is already a result for this block, no need to validate it
        if self
            .block_validation_results
            .get(&block.header_signature)
            .is_some()
        {
            return;
        }

        // Create block validation result, maked as in-validation
        self.block_validation_results.insert(BlockValidationResult {
            block_id: block.header_signature.clone(),
            execution_results: vec![],
            num_transactions: 0,
            status: BlockStatus::InValidation,
        });

        // Submit for validation
        let sender = self.validation_result_sender.as_ref().expect(
            "Attempted to submit block for validation before starting the chain controller",
        );
        self.block_validator
            .submit_blocks_for_verification(&[block.clone()], &sender);
    }

    pub fn ignore_block(&self, block: &Block) {
        let mut state = self
            .state
            .write()
            .expect("No lock holder should have poisoned the lock");

        // Drop Ref-C: Consensus is not interested in this block anymore
        match state.block_references.remove(&block.header_signature) {
            Some(_) => info!("Ignored block {}", block),
            None => debug!(
                "Could not ignore block {}; consensus has already decided on it",
                &block.header_signature
            ),
        }
    }

    pub fn fail_block(&self, block: &Block) {
        let mut state = self
            .state
            .write()
            .expect("No lock holder should have poisoned the lock");

        // Drop Ref-C: Consensus is not interested in this block anymore
        match state.block_references.remove(&block.header_signature) {
            Some(_) => {
                self.block_validation_results
                    .fail_block(&block.header_signature);
                info!("Failed block {}", block);
            }
            None => debug!(
                "Could not fail block {}; consensus has already decided on it",
                &block.header_signature
            ),
        }
    }

    // Returns all blocks in forks not on the chain with the given head. If head is None, uses the
    // current chain head. If head is not found, returns None.
    pub fn forks(&self, head: &str) -> Option<Vec<Block>> {
        let state = self
            .state
            .read()
            .expect("No lock holder should have poisoned the lock");

        let block_ref = match state.block_manager.ref_block(head) {
            Ok(block_ref) => Some(block_ref),
            Err(BlockManagerError::UnknownBlock) => None,
            Err(err) => {
                error!("Unexpected error occurred: {:?}", err);
                None
            }
        };

        if block_ref.is_none() {
            return None;
        }

        let mut forks: Vec<Block> = state
            .fork_cache
            .forks()
            .into_iter()
            .flat_map(|fork_head: &String| {
                state
                    .block_manager
                    .branch_diff(fork_head, head)
                    .expect("Fork not found, but should be referenced")
            })
            .collect();

        forks.sort_by(|left, right| {
            left.block_num
                .cmp(&right.block_num)
                .then(left.header_signature.cmp(&right.header_signature))
        });
        forks.dedup_by(|left, right| left.header_signature == right.header_signature);

        Some(forks)
    }

    fn set_block_validation_result(&self, result: BlockValidationResult) {
        self.block_validation_results.insert(result)
    }

    fn get_block(&self, block_id: &str) -> Option<Block> {
        let state = self
            .state
            .read()
            .expect("No lock holder should have poisoned the lock");

        state.block_manager.get(&[block_id]).next().unwrap_or(None)
    }

    pub fn commit_block(&self, block: Block) {
        if let Some(sender) = self.commit_queue_sender.as_ref() {
            if let Err(err) = sender.send(block) {
                error!("Unable to add block to block queue: {}", err);
            }
        } else {
            debug!(
                "Attempting to commit block {} before chain controller is started; Ignoring",
                block
            );
        }
    }

    fn on_block_validated(&self, block: &Block, result: &BlockValidationResult) {
        let mut blocks_considered_count =
            COLLECTOR.counter("ChainController.blocks_considered_count", None, None);
        blocks_considered_count.inc();

        match result.status {
            BlockStatus::Valid => {
                // Keep Ref-C: The block has been validated so ownership of the ext. ref. is
                // maintained. The consensus engine is responsible for rendering an opinion of
                // either commit, fail, or ignore, at which time the ext. ref. will be accounted
                // for (moved into chain head in case of commit, dropped otherwise)
                self.consensus_notifier
                    .notify_block_valid(&block.header_signature);
            }
            BlockStatus::Invalid => {
                self.consensus_notifier
                    .notify_block_invalid(&block.header_signature);

                let mut state = self
                    .state
                    .write()
                    .expect("No lock holder should have poisoned the lock");

                // Drop Ref-C: The block has been found to be invalid, and we are no longer
                // interested in it. The invalid result will be cached for a period.
                if state
                    .block_references
                    .remove(&block.header_signature)
                    .is_none()
                {
                    error!(
                        "Reference not found for invalid block {}",
                        &block.header_signature
                    );
                }
            }
            _ => error!(
                "on_block_validated() called for block {}, but result was {:?}",
                block.header_signature, result.status,
            ),
        }

        match self.notify_block_validation_results_received(&block) {
            Ok(_) => (),
            Err(err) => warn!("{:?}", err),
        }
    }

    fn handle_block_commit(&mut self, block: &Block) -> Result<(), ChainControllerError> {
        {
            // only hold this lock as long as the loop is active.
            let mut state = self
                .state
                .write()
                .expect("No lock holder should have poisoned the lock");

            loop {
                let chain_head = state
                    .chain_reader
                    .chain_head()
                    .map_err(|err| {
                        error!("Error reading chain head: {:?}", err);
                        err
                    })?
                    .expect(
                        "Attempting to handle block commit before a genesis block has been
                        committed",
                    );
                let result = state.build_fork(block, &chain_head).map_err(|err| {
                    error!(
                        "Error occured while building fork resolution result: {:?}",
                        err,
                    );
                    err
                })?;

                let mut chain_head_guard = self.chain_head_lock.acquire();
                let chain_head_updated = state
                    .check_chain_head_updated(&chain_head, block)
                    .map_err(|err| {
                        error!(
                            "Error occured while checking if chain head updated: {:?}",
                            err,
                        );
                        err
                    })?;
                if chain_head_updated {
                    continue;
                }

                // Move Ref-C: Consensus has decided this block should become the new chain
                // head, so the ChainController will maintain ownership of this ext. ref until a
                // new chain head replaces it.
                state.chain_head = Some(
                    state
                        .block_references
                        .remove(&block.header_signature)
                        .ok_or_else(|| {
                            ChainControllerError::ConsensusError(
                                "Consensus has already decided on this block".into(),
                            )
                        })?,
                );

                let new_roots: Vec<String> = result
                    .new_chain
                    .iter()
                    .map(|block| block.state_root_hash.clone())
                    .collect();
                let current_roots: Vec<(u64, String)> = result
                    .current_chain
                    .iter()
                    .map(|block| (block.block_num, block.state_root_hash.clone()))
                    .collect();
                state.state_pruning_manager.update_queue(
                    new_roots
                        .iter()
                        .map(|root| root.as_str())
                        .collect::<Vec<_>>()
                        .as_slice(),
                    current_roots
                        .iter()
                        .map(|(num, root)| (*num, root.as_str()))
                        .collect::<Vec<_>>()
                        .as_slice(),
                );

                state
                    .block_manager
                    .persist(&block.header_signature, COMMIT_STORE)
                    .map_err(|err| {
                        error!("Error persisting new chain head: {:?}", err);
                        err
                    })?;

                info!("Chain head updated to {}", &block);

                self.consensus_notifier
                    .notify_block_commit(&block.header_signature);

                let mut chain_head_gauge =
                    COLLECTOR.gauge("ChainController.chain_head", None, None);
                chain_head_gauge.set_value(&block.header_signature[0..8]);

                let mut committed_transactions_count =
                    COLLECTOR.counter("ChainController.committed_transactions_count", None, None);
                committed_transactions_count.inc_n(result.transaction_count);

                let mut block_num_guage = COLLECTOR.gauge("ChainController.block_num", None, None);
                block_num_guage.set_value(block.block_num);

                chain_head_guard.notify_on_chain_updated(
                    block.clone(),
                    result.committed_batches,
                    result.uncommitted_batches,
                );

                block.batches.iter().for_each(|batch| {
                    if batch.trace {
                        debug!(
                            "TRACE: {}: ChainController.on_block_validated",
                            batch.header_signature
                        )
                    }
                });

                for blk in result.new_chain.iter().rev() {
                    match self.block_validation_results.get(&blk.header_signature) {
                        Some(validation_results) => {
                            let receipts: Vec<TransactionReceipt> = validation_results
                                .execution_results
                                .iter()
                                .map(TransactionReceipt::from)
                                .collect();
                            for observer in &mut state.observers {
                                observer.chain_update(&block, receipts.as_slice());
                            }
                        }
                        None => {
                            error!(
                                "While committing {}, found block {} missing execution results",
                                &block, &blk,
                            );
                        }
                    }
                }

                let total_committed_txns = match state.chain_reader.count_committed_transactions() {
                    Ok(count) => count,
                    Err(err) => {
                        error!(
                            "Unable to read total committed transactions count: {:?}",
                            err
                        );
                        0
                    }
                };

                let mut committed_transactions_gauge =
                    COLLECTOR.gauge("ChainController.committed_transactions_gauge", None, None);
                committed_transactions_gauge.set_value(total_committed_txns);

                let chain_head_block_num = block.block_num;
                if chain_head_block_num + 1 > u64::from(self.state_pruning_block_depth) {
                    let prune_at =
                        chain_head_block_num - (u64::from(self.state_pruning_block_depth));
                    match state.chain_reader.get_block_by_block_num(prune_at) {
                        Ok(Some(block)) => state
                            .state_pruning_manager
                            .add_to_queue(block.block_num, &block.state_root_hash),
                        Ok(None) => warn!("No block at block height {}; ignoring...", prune_at),
                        Err(err) => {
                            error!("Unable to fetch block at height {}: {:?}", prune_at, err)
                        }
                    }

                    // Execute pruning:
                    state.state_pruning_manager.execute(prune_at)
                }

                // Updated the block, so we're done
                break;
            }
        }

        Ok(())
    }

    /// Light clone makes a copy of this controller, without access to the stop
    /// handle.
    pub fn light_clone(&self) -> Self {
        ChainController {
            state: self.state.clone(),
            // This instance doesn't share the stop handle: it's not a
            // publicly accessible instance
            stop_handle: Arc::new(Mutex::new(None)),
            block_validator: self.block_validator.clone(),
            block_validation_results: self.block_validation_results.clone(),
            block_queue_sender: self.block_queue_sender.clone(),
            commit_queue_sender: self.commit_queue_sender.clone(),
            validation_result_sender: self.validation_result_sender.clone(),
            state_pruning_block_depth: self.state_pruning_block_depth,
            chain_head_lock: self.chain_head_lock.clone(),
            consensus_notifier: self.consensus_notifier.clone(),
            consensus_registry: self.consensus_registry.clone(),
            state_view_factory: self.state_view_factory.clone(),
        }
    }

    fn notify_block_validation_results_received(
        &self,
        block: &Block,
    ) -> Result<(), ChainControllerError> {
        let sender = self
            .validation_result_sender
            .as_ref()
            .expect("Unable to ref validation_result_sender");

        self.block_validator.process_pending(block, &sender);
        Ok(())
    }

    pub fn queue_block(&self, block_id: &str) {
        if self.block_queue_sender.is_some() {
            let sender = self.block_queue_sender.clone();
            if let Err(err) = sender.as_ref().unwrap().send(block_id.into()) {
                error!("Unable to add block to block queue: {}", err);
            }
        } else {
            debug!(
                "Attempting to queue block {} before chain controller is started; Ignoring",
                block_id
            );
        }
    }

    fn initialize_chain_head(&mut self) {
        // we need to check to see if a genesis block was created and stored,
        // before this controller was started
        let mut state = self
            .state
            .write()
            .expect("No lock holder should have poisoned the lock");

        let chain_head = state
            .chain_reader
            .chain_head()
            .expect("Invalid block store. Head of the block chain cannot be determined");

        if let Some(chain_head) = chain_head {
            info!(
                "Chain controller initialized with chain head: {}",
                &chain_head
            );

            // Create Ref-C: External reference for the chain head will be held until it is
            // superceded by a new chain head.
            state.chain_head = Some(
                state
                    .block_manager
                    .ref_block(chain_head.header_signature.as_str())
                    .expect("Failed to reference chain head"),
            );

            let mut gauge = COLLECTOR.gauge("ChainController.chain_head", None, None);
            gauge.set_value(&chain_head.header_signature[0..8]);

            let mut block_num_guage = COLLECTOR.gauge("ChainController.block_num", None, None);
            block_num_guage.set_value(&chain_head.block_num);
            let mut guard = self.chain_head_lock.acquire();

            guard.notify_on_chain_updated(chain_head, vec![], vec![]);
        }
    }

    pub fn start(&mut self) {
        // duplicating what happens at the constructor time, but there are multiple
        // points in the lifetime of this object where the value of the
        // block store's chain head may have been set
        self.initialize_chain_head();
        let mut stop_handle = self.stop_handle.lock().unwrap();
        if stop_handle.is_none() {
            let (block_queue_sender, block_queue_receiver) = channel();
            let (validation_result_sender, validation_result_receiver) = channel();
            let (commit_queue_sender, commit_queue_receiver) = channel();

            self.block_queue_sender = Some(block_queue_sender);
            self.validation_result_sender = Some(validation_result_sender);
            self.commit_queue_sender = Some(commit_queue_sender);

            let thread_chain_controller = self.light_clone();
            let exit_flag = Arc::new(AtomicBool::new(false));
            let mut chain_thread = ChainThread::new(
                thread_chain_controller,
                block_queue_receiver,
                exit_flag.clone(),
            );
            *stop_handle = Some(ChainThreadStopHandle::new(exit_flag.clone()));
            let chain_thread_builder =
                thread::Builder::new().name("ChainThread:BlockReceiver".into());
            chain_thread_builder
                .spawn(move || {
                    if let Err(err) = chain_thread.run() {
                        error!("Error occurred during ChainController loop: {:?}", err);
                    }
                })
                .unwrap();

            self.start_validation_result_thread(exit_flag.clone(), validation_result_receiver);
            self.start_commit_queue_thread(exit_flag.clone(), commit_queue_receiver);
        }
    }

    fn start_validation_result_thread(
        &self,
        result_thread_exit: Arc<AtomicBool>,
        validation_result_receiver: Receiver<BlockValidationResult>,
    ) {
        // Setup the ValidationResult thread
        let result_thread_builder =
            thread::Builder::new().name("ChainThread:ValidationResultReceiver".into());
        let result_thread_controller = self.light_clone();
        result_thread_builder
            .spawn(move || loop {
                let block_validation_result = match validation_result_receiver
                    .recv_timeout(Duration::from_millis(RECV_TIMEOUT_MILLIS))
                {
                    Err(mpsc::RecvTimeoutError::Timeout) => {
                        if result_thread_exit.load(Ordering::Relaxed) {
                            break;
                        } else {
                            continue;
                        }
                    }
                    Err(_) => {
                        error!("Result queue shutdown unexpectedly");
                        break;
                    }
                    Ok(res) => res,
                };

                if !result_thread_exit.load(Ordering::Relaxed) {
                    result_thread_controller
                        .set_block_validation_result(block_validation_result.clone());
                    if let Some(block) = result_thread_controller
                        .get_block(&block_validation_result.block_id) {
                            result_thread_controller.on_block_validated(&block, &block_validation_result);
                        } else {
                            error!("During validation result thread loop, received a block validation result for a block that is not in the BlockManager");
                        }

                } else {
                    break;
                }
            }).unwrap();
    }

    fn start_commit_queue_thread(
        &self,
        commit_thread_exit: Arc<AtomicBool>,
        commit_queue_receiver: Receiver<Block>,
    ) {
        // Setup the Commit thread:
        let commit_thread_builder =
            thread::Builder::new().name("ChainThread:CommitReceiver".into());
        let mut commit_thread_controller = self.light_clone();
        commit_thread_builder
            .spawn(move || loop {
                let block = match commit_queue_receiver
                    .recv_timeout(Duration::from_millis(RECV_TIMEOUT_MILLIS))
                {
                    Err(mpsc::RecvTimeoutError::Timeout) => {
                        if commit_thread_exit.load(Ordering::Relaxed) {
                            break;
                        } else {
                            continue;
                        }
                    }
                    Err(_) => {
                        error!("Commit queue shutdown unexpectedly");
                        break;
                    }
                    Ok(res) => res,
                };

                if !commit_thread_exit.load(Ordering::Relaxed) {
                    if let Err(err) = commit_thread_controller.handle_block_commit(&block) {
                        error!(
                            "An error occurred while committing block {}: {:?}",
                            block, err
                        );
                    }
                } else {
                    break;
                }
            })
            .unwrap();
    }

    pub fn stop(&mut self) {
        let mut stop_handle = self.stop_handle.lock().unwrap();
        if stop_handle.is_some() {
            let handle: ChainThreadStopHandle = stop_handle.take().unwrap();
            handle.stop();
        }
    }
}

impl<'a> From<&'a TxnExecutionResult> for TransactionReceipt {
    fn from(result: &'a TxnExecutionResult) -> Self {
        let mut receipt = TransactionReceipt::new();

        receipt.set_data(protobuf::RepeatedField::from_vec(
            result.data.iter().map(|data| data.clone()).collect(),
        ));
        receipt.set_state_changes(protobuf::RepeatedField::from_vec(
            result.state_changes.clone(),
        ));
        receipt.set_events(protobuf::RepeatedField::from_vec(result.events.clone()));
        receipt.set_transaction_id(result.signature.clone());

        receipt
    }
}

struct ChainThread<TEP: ExecutionPlatform + Clone, PV: PermissionVerifier + Clone> {
    chain_controller: ChainController<TEP, PV>,
    block_queue: Receiver<String>,
    exit: Arc<AtomicBool>,
}

trait StopHandle: Clone {
    fn stop(&self);
}

impl<TEP: ExecutionPlatform + Clone + 'static, PV: PermissionVerifier + Clone + 'static>
    ChainThread<TEP, PV>
{
    fn new(
        chain_controller: ChainController<TEP, PV>,
        block_queue: Receiver<String>,
        exit_flag: Arc<AtomicBool>,
    ) -> Self {
        ChainThread {
            chain_controller,
            block_queue,
            exit: exit_flag,
        }
    }

    fn run(&mut self) -> Result<(), ChainControllerError> {
        loop {
            let block_id = match self
                .block_queue
                .recv_timeout(Duration::from_millis(RECV_TIMEOUT_MILLIS))
            {
                Err(mpsc::RecvTimeoutError::Timeout) => {
                    if self.exit.load(Ordering::Relaxed) {
                        break Ok(());
                    } else {
                        continue;
                    }
                }
                Err(_) => break Err(ChainControllerError::BrokenQueue),
                Ok(block_id) => block_id,
            };
            self.chain_controller.on_block_received(&block_id)?;

            if self.exit.load(Ordering::Relaxed) {
                break Ok(());
            }
        }
    }
}

#[derive(Clone)]
struct ChainThreadStopHandle {
    exit: Arc<AtomicBool>,
}

impl ChainThreadStopHandle {
    fn new(exit_flag: Arc<AtomicBool>) -> Self {
        ChainThreadStopHandle { exit: exit_flag }
    }
}

impl StopHandle for ChainThreadStopHandle {
    fn stop(&self) {
        self.exit.store(true, Ordering::Relaxed)
    }
}

#[cfg(tests)]
mod tests {}
