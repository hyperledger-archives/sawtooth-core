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
use journal;
use journal::block_validator::{BlockValidator, ValidationError};
use journal::block_wrapper::{BlockStatus, BlockWrapper};
use journal::chain_head_lock::ChainHeadLock;
use journal::chain_id_manager::ChainIdManager;
use metrics;
use state::state_pruning_manager::StatePruningManager;

use proto::transaction_receipt::TransactionReceipt;
use scheduler::TxnExecutionResult;

const RECV_TIMEOUT_MILLIS: u64 = 100;

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

pub trait ChainObserver: Send + Sync {
    fn chain_update(&mut self, block: &BlockWrapper, receipts: &[&TransactionReceipt]);
}

pub trait BlockCache: Send + Sync {
    fn contains(&self, block_id: &str) -> bool;

    fn put(&mut self, block: BlockWrapper);

    fn get(&self, block_id: &str) -> Option<BlockWrapper>;

    fn iter(&self) -> Box<Iterator<Item = BlockWrapper>>;
}

#[derive(Debug)]
pub enum ChainReadError {
    GeneralReadError(String),
}

pub trait ChainReader: Send + Sync {
    fn chain_head(&self) -> Result<Option<BlockWrapper>, ChainReadError>;
    fn count_committed_transactions(&self) -> Result<usize, ChainReadError>;
    fn get_block_by_block_num(
        &self,
        block_num: u64,
    ) -> Result<Option<BlockWrapper>, ChainReadError>;
}

pub trait ChainWriter: Send + Sync {
    fn update_chain(
        &mut self,
        new_chain: &[BlockWrapper],
        old_chain: &[BlockWrapper],
    ) -> Result<(), ChainControllerError>;
}

pub trait ConsensusNotifier: Send + Sync {
    fn notify_block_new(&self, block: &BlockWrapper);
    fn notify_block_valid(&self, block_id: &str);
    fn notify_block_invalid(&self, block_id: &str);
    fn notify_block_commit(&self, block_id: &str);
}

/// Holds the results of Block Validation.
struct ForkResolutionResult<'a> {
    pub block: &'a BlockWrapper,
    pub chain_head: &'a Option<BlockWrapper>,

    pub new_chain: Vec<BlockWrapper>,
    pub current_chain: Vec<BlockWrapper>,

    pub committed_batches: Vec<Batch>,
    pub uncommitted_batches: Vec<Batch>,

    pub transaction_count: usize,
}

impl<'a> ForkResolutionResult<'a> {
    fn new(block: &'a BlockWrapper) -> Self {
        ForkResolutionResult {
            block,
            chain_head: &None,
            new_chain: vec![],
            current_chain: vec![],
            committed_batches: vec![],
            uncommitted_batches: vec![],
            transaction_count: 0,
        }
    }
}

/// Indication that an error occured during fork resolution.
#[derive(Debug)]
struct ForkResolutionError(String);

struct ChainControllerState<BC: BlockCache, BV: BlockValidator> {
    block_cache: BC,
    block_validator: BV,
    chain_writer: Box<ChainWriter>,
    chain_reader: Box<ChainReader>,
    chain_head: Option<BlockWrapper>,
    chain_id_manager: ChainIdManager,
    observers: Vec<Box<ChainObserver>>,
    state_pruning_manager: StatePruningManager,
}

impl<BC: BlockCache, BV: BlockValidator> ChainControllerState<BC, BV> {
    fn has_block(&self, block_id: &str) -> bool {
        self.block_cache.contains(block_id) || self.block_validator.has_block(block_id)
    }

    /// This is used by a non-genesis journal when it has received the
    /// genesis block from the genesis validator
    fn set_genesis(
        &mut self,
        lock: &ChainHeadLock,
        block: BlockWrapper,
    ) -> Result<(), ChainControllerError> {
        if block.previous_block_id() == journal::NULL_BLOCK_IDENTIFIER {
            let chain_id = self.chain_id_manager.get_block_chain_id()?;
            if chain_id
                .as_ref()
                .map(|block_id| block_id != &block.header_signature())
                .unwrap_or(false)
            {
                warn!(
                    "Block id does not match block chain id {}. Ignoring initial chain head: {}",
                    chain_id.unwrap(),
                    block.header_signature()
                );
            } else {
                self.block_validator.validate_block(block.clone())?;

                if chain_id.is_none() {
                    self.chain_id_manager
                        .save_block_chain_id(&block.header_signature())?;
                }

                self.chain_writer.update_chain(&[block.clone()], &[])?;
                self.chain_head = Some(block.clone());
                let mut guard = lock.acquire();
                guard.notify_on_chain_updated(block.clone(), vec![], vec![]);
            }
        }

        Ok(())
    }

    fn build_fork<'a>(
        &mut self,
        block: &'a BlockWrapper,
        chain_head: &'a BlockWrapper,
    ) -> Result<ForkResolutionResult<'a>, ChainControllerError> {
        let mut result = ForkResolutionResult::new(block);

        let mut current_block = chain_head.clone();
        let mut new_block = block.clone();

        let chain_comparison = compare_chain_height(&current_block, &new_block);
        let (compared_block, chain) = if chain_comparison {
            self.build_fork_diff_to_common_height(&current_block, &new_block)?
        } else {
            self.build_fork_diff_to_common_height(&new_block, &current_block)?
        };

        if chain_comparison {
            current_block = compared_block;
            result.current_chain = chain;
        } else {
            new_block = compared_block;
            result.new_chain = chain;
        }

        self.extend_fork_diff_to_common_anscestor(
            &new_block,
            &current_block,
            &mut result.new_chain,
            &mut result.current_chain,
        )?;

        result.transaction_count = result.new_chain.iter().map(|b| b.num_transactions()).sum();

        info!(
            "Building fork resolution for chain head '{}' against new block '{}'",
            &chain_head, &block
        );

        let (commit, uncommit) = get_batch_commit_changes(&result.new_chain, &result.current_chain);
        result.committed_batches = commit;
        result.uncommitted_batches = uncommit;

        if result.new_chain.is_empty() {
            return Err(ChainControllerError::ForkResolutionError(
                "On fork comparison, new chain is empty".into(),
            ));
        }

        if result.new_chain[0].previous_block_id() != chain_head.header_signature() {
            let mut moved_to_fork_count =
                COLLECTOR.counter("ChainController.chain_head_moved_to_fork_count", None, None);
            moved_to_fork_count.inc();
        }

        Ok(result)
    }

    fn build_fork_diff_to_common_height<'a>(
        &self,
        head_long: &BlockWrapper,
        head_short: &BlockWrapper,
    ) -> Result<(BlockWrapper, Vec<BlockWrapper>), ForkResolutionError> {
        let mut fork_diff = vec![];

        let last = head_short.block_num();
        let mut block = head_long.clone();

        loop {
            if block.block_num() == last
                || block.previous_block_id() == journal::NULL_BLOCK_IDENTIFIER
            {
                return Ok((block, fork_diff));
            }

            fork_diff.push(block.clone());

            block = self
                .get_from_cache_strict(&block.previous_block_id(), "Failed to build fork diff")?;
        }
    }

    /// Returns a block from the cache, or an error if it is not found
    fn get_from_cache_strict(
        &self,
        block_id: &str,
        error_msg_prefix: &'static str,
    ) -> Result<BlockWrapper, ForkResolutionError> {
        match self.block_cache.get(block_id) {
            Some(block) => Ok(block),
            None => {
                return Err(ForkResolutionError(format!(
                    "{}: block missing predecessor {}",
                    error_msg_prefix, block_id
                )))
            }
        }
    }

    /// Finds a common ancestor of the two chains. new_blkw and cur_blkw must be
    /// at the same height, or this will always fail.
    fn extend_fork_diff_to_common_anscestor(
        &mut self,
        new_block: &BlockWrapper,
        cur_block: &BlockWrapper,
        new_chain: &mut Vec<BlockWrapper>,
        cur_chain: &mut Vec<BlockWrapper>,
    ) -> Result<(), ForkResolutionError> {
        let mut new = new_block.clone();
        let mut current = cur_block.clone();

        while current.header_signature() != new.header_signature() {
            if current.previous_block_id() == journal::NULL_BLOCK_IDENTIFIER
                || new.previous_block_id() == journal::NULL_BLOCK_IDENTIFIER
            {
                loop {
                    match new_chain.pop() {
                        Some(mut block) => {
                            block.set_status(BlockStatus::Invalid);
                            // need to put it back in the cache
                            self.block_cache.put(block);
                        }
                        None => break,
                    }
                }

                return Err(ForkResolutionError(format!(
                    "Block {} rejected due to wrong genesis {}",
                    current, new
                )));
            }

            new_chain.push(new);
            new = self.get_from_cache_strict(
                &new_chain.last().unwrap().previous_block_id(),
                "Failed to extend new chain",
            )?;

            cur_chain.push(current);
            current = self
                .block_cache
                .get(&cur_chain.last().unwrap().previous_block_id())
                .expect("Could not find current chain predecessor in block cache");
        }

        Ok(())
    }

    fn check_chain_head_updated(
        &self,
        chain_head: &BlockWrapper,
        block: &BlockWrapper,
    ) -> Result<bool, ChainControllerError> {
        let current_chain_head = self.chain_reader.chain_head()?;
        if current_chain_head
            .as_ref()
            .map(|block| block.header_signature() != chain_head.header_signature())
            .unwrap_or(false)
        {
            warn!(
                "Chain head updated from {} to {} while resolving \
                 fork for block {}. Reprocessing resolution.",
                chain_head,
                current_chain_head.as_ref().unwrap(),
                block
            );
            return Ok(true);
        }

        return Ok(false);
    }
}

/// Returns true if head_a is taller, false if head_b is taller, and true if
/// the heights are the same.
fn compare_chain_height(block_a: &BlockWrapper, block_b: &BlockWrapper) -> bool {
    block_a.block_num() >= block_b.block_num()
}

/// Get all the batches that should be committed from the new chain and
/// all the batches that should be uncommitted from the current chain.
fn get_batch_commit_changes(
    new_chain: &[BlockWrapper],
    cur_chain: &[BlockWrapper],
) -> (Vec<Batch>, Vec<Batch>) {
    let mut committed_batches = vec![];
    for block in new_chain {
        for batch in block.batches() {
            committed_batches.push(batch.clone());
        }
    }

    let mut uncommitted_batches = vec![];
    for block in cur_chain {
        for batch in block.batches() {
            uncommitted_batches.push(batch.clone());
        }
    }

    (committed_batches, uncommitted_batches)
}

#[derive(Clone)]
pub struct ChainController<BC: BlockCache, BV: BlockValidator> {
    state: Arc<RwLock<ChainControllerState<BC, BV>>>,
    stop_handle: Arc<Mutex<Option<ChainThreadStopHandle>>>,

    consensus_notifier: Arc<ConsensusNotifier>,

    // Queues
    block_queue_sender: Option<Sender<BlockWrapper>>,
    commit_queue_sender: Option<Sender<BlockWrapper>>,
    validation_result_sender: Option<Sender<BlockWrapper>>,

    state_pruning_block_depth: u32,
    chain_head_lock: ChainHeadLock,
}

impl<BC: BlockCache + 'static, BV: BlockValidator + 'static> ChainController<BC, BV> {
    pub fn new(
        block_cache: BC,
        block_validator: BV,
        chain_writer: Box<ChainWriter>,
        chain_reader: Box<ChainReader>,
        chain_head_lock: ChainHeadLock,
        consensus_notifier: Box<ConsensusNotifier>,
        data_dir: String,
        state_pruning_block_depth: u32,
        observers: Vec<Box<ChainObserver>>,
        state_pruning_manager: StatePruningManager,
    ) -> Self {
        let mut chain_controller = ChainController {
            state: Arc::new(RwLock::new(ChainControllerState {
                block_cache,
                block_validator,
                chain_writer,
                chain_reader,
                chain_id_manager: ChainIdManager::new(data_dir),
                observers,
                chain_head: None,
                state_pruning_manager,
            })),
            stop_handle: Arc::new(Mutex::new(None)),
            block_queue_sender: None,
            commit_queue_sender: None,
            validation_result_sender: None,
            state_pruning_block_depth,
            chain_head_lock,
            consensus_notifier: Arc::from(consensus_notifier),
        };

        chain_controller.initialize_chain_head();

        chain_controller
    }

    pub fn chain_head(&self) -> Option<BlockWrapper> {
        let state = self
            .state
            .read()
            .expect("No lock holder should have poisoned the lock");

        state.chain_head.clone()
    }

    pub fn on_block_received(&mut self, block: BlockWrapper) -> Result<(), ChainControllerError> {
        let mut state = self
            .state
            .write()
            .expect("No lock holder should have poisoned the lock");

        if state.has_block(&block.header_signature()) {
            return Ok(());
        }

        if state.chain_head.is_none() {
            if let Err(err) = state.set_genesis(&self.chain_head_lock, block.clone()) {
                warn!(
                    "Unable to set chain head; genesis block {} is not valid: {:?}",
                    block.header_signature(),
                    err
                );
            }
            return Ok(());
        }

        state.block_cache.put(block.clone());
        let sender = self
            .validation_result_sender
            .as_ref()
            .expect(
                "Attempted to submit blocks for validation before starting the chain controller",
            ).clone();

        state
            .block_validator
            .submit_blocks_for_verification(&[block], sender);

        Ok(())
    }

    pub fn has_block(&self, block_id: &str) -> bool {
        let state = self
            .state
            .read()
            .expect("No lock holder should have poisoned the lock");
        state.has_block(block_id)
    }

    pub fn ignore_block(&self, block: &BlockWrapper) {
        info!("Ignoring block {}", block)
    }

    // Returns all valid blocks in forks not on the chain with the given head. If head is None,
    // uses the current chain head. If head is not found, returns None.
    pub fn forks(&self) -> Vec<BlockWrapper> {
        let state = self
            .state
            .read()
            .expect("No lock holder should have poisoned the lock");

        let mut forks: Vec<BlockWrapper> = state.block_cache.iter().collect();

        forks.sort_by(|left, right| {
            left.block_num()
                .cmp(&right.block_num())
                .then(left.header_signature().cmp(&right.header_signature()))
        });
        forks.dedup_by(|left, right| left.header_signature() == right.header_signature());

        forks
            .into_iter()
            .filter(|blockw| blockw.status() == BlockStatus::Valid)
            .collect()
    }

    pub fn fail_block(&self, block: &mut BlockWrapper) {
        let mut state = self
            .state
            .write()
            .expect("No lock holder should have poisoned the lock");

        block.set_status(BlockStatus::Invalid);

        state.block_cache.put(block.clone());
    }

    pub fn commit_block(&self, block: BlockWrapper) {
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

    fn on_block_validated(&self, block: &BlockWrapper) {
        let mut blocks_considered_count =
            COLLECTOR.counter("ChainController.blocks_considered_count", None, None);
        blocks_considered_count.inc();

        self.consensus_notifier.notify_block_new(block);
    }

    fn handle_block_commit(&mut self, block: &BlockWrapper) -> Result<(), ChainControllerError> {
        {
            // only hold this lock as long as the loop is active.
            let mut state = self
                .state
                .write()
                .expect("No lock holder should have poisoned the lock");

            loop {
                let chain_head = state.chain_reader.chain_head()?.expect(
                    "Attempting to handle block commit before a genesis block has been committed",
                );
                let result = state.build_fork(block, &chain_head)?;

                let mut chain_head_guard = self.chain_head_lock.acquire();
                if state.check_chain_head_updated(&chain_head, block)? {
                    continue;
                }

                state.chain_head = Some(block.clone());

                let new_roots: Vec<String> = result
                    .new_chain
                    .iter()
                    .map(|block| block.state_root_hash())
                    .collect();
                let current_roots: Vec<(u64, String)> = result
                    .current_chain
                    .iter()
                    .map(|block| (block.block_num(), block.state_root_hash()))
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
                    .chain_writer
                    .update_chain(&result.new_chain, &result.current_chain)?;

                info!(
                    "Chain head updated to {}",
                    state.chain_head.as_ref().unwrap()
                );

                let mut chain_head_gauge =
                    COLLECTOR.gauge("ChainController.chain_head", None, None);
                chain_head_gauge.set_value(&block.header_signature()[0..8]);

                let mut committed_transactions_count =
                    COLLECTOR.counter("ChainController.committed_transactions_count", None, None);
                committed_transactions_count.inc_n(result.transaction_count);

                let mut block_num_guage = COLLECTOR.gauge("ChainController.block_num", None, None);
                block_num_guage.set_value(block.block_num());

                let chain_head = state.chain_head.clone().unwrap();
                chain_head_guard.notify_on_chain_updated(
                    chain_head,
                    result.committed_batches,
                    result.uncommitted_batches,
                );

                state.chain_head.as_ref().map(|block| {
                    block.batches().iter().for_each(|batch| {
                        if batch.trace {
                            debug!(
                                "TRACE: {}: ChainController.on_block_validated",
                                batch.header_signature
                            )
                        }
                    })
                });

                for block in result.new_chain.iter().rev() {
                    let receipts: Vec<TransactionReceipt> = block
                        .execution_results()
                        .iter()
                        .map(TransactionReceipt::from)
                        .collect();
                    for observer in state.observers.iter_mut() {
                        observer.chain_update(&block, &receipts.iter().collect::<Vec<_>>());
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

                let chain_head_block_num = state.chain_head.as_ref().unwrap().block_num();
                if chain_head_block_num + 1 > self.state_pruning_block_depth as u64 {
                    let prune_at = chain_head_block_num - (self.state_pruning_block_depth as u64);
                    match state.chain_reader.get_block_by_block_num(prune_at) {
                        Ok(Some(block)) => state
                            .state_pruning_manager
                            .add_to_queue(block.block_num(), &block.state_root_hash()),
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

        self.consensus_notifier
            .notify_block_commit(&block.header_signature());

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
            block_queue_sender: self.block_queue_sender.clone(),
            commit_queue_sender: self.commit_queue_sender.clone(),
            validation_result_sender: self.validation_result_sender.clone(),
            state_pruning_block_depth: self.state_pruning_block_depth,
            chain_head_lock: self.chain_head_lock.clone(),
            consensus_notifier: self.consensus_notifier.clone(),
        }
    }

    pub fn submit_blocks_for_verification(
        &self,
        blocks: &[BlockWrapper],
    ) -> Result<(), ChainControllerError> {
        let sender = self
            .validation_result_sender
            .as_ref()
            .expect(
                "Attempted to submit blocks for validation before starting the chain controller",
            ).clone();

        self.state
            .write()
            .expect("No lock holder should have poisoned the lock")
            .block_validator
            .submit_blocks_for_verification(blocks, sender);
        Ok(())
    }

    pub fn queue_block(&self, block: BlockWrapper) {
        if self.block_queue_sender.is_some() {
            let sender = self.block_queue_sender.clone();
            if let Err(err) = sender.as_ref().unwrap().send(block) {
                error!("Unable to add block to block queue: {}", err);
            }
        } else {
            debug!(
                "Attempting to queue block {} before chain controller is started; Ignoring",
                block
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

        if chain_head.is_some() {
            info!(
                "Chain controller initialized with chain head: {}",
                chain_head.as_ref().unwrap()
            );
            let notify_block = chain_head.clone().unwrap();
            state.chain_head = chain_head;
            let mut gauge = COLLECTOR.gauge("ChainController.chain_head", None, None);
            gauge.set_value(&notify_block.header_signature()[0..8]);

            let mut block_num_guage = COLLECTOR.gauge("ChainController.block_num", None, None);
            block_num_guage.set_value(&notify_block.block_num());
            let mut guard = self.chain_head_lock.acquire();
            guard.notify_on_chain_updated(notify_block, vec![], vec![]);
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
                }).unwrap();

            self.start_validation_result_thread(exit_flag.clone(), validation_result_receiver);
            self.start_commit_queue_thread(exit_flag.clone(), commit_queue_receiver);
        }
    }

    fn start_validation_result_thread(
        &self,
        result_thread_exit: Arc<AtomicBool>,
        validation_result_receiver: Receiver<BlockWrapper>,
    ) {
        // Setup the ValidationResult thread
        let result_thread_builder =
            thread::Builder::new().name("ChainThread:ValidationResultReceiver".into());
        let result_thread_controller = self.light_clone();
        result_thread_builder
            .spawn(move || loop {
                let block = match validation_result_receiver
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
                    result_thread_controller.on_block_validated(&block);
                } else {
                    break;
                }
            }).unwrap();
    }

    fn start_commit_queue_thread(
        &self,
        commit_thread_exit: Arc<AtomicBool>,
        commit_queue_receiver: Receiver<BlockWrapper>,
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
            }).unwrap();
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

struct ChainThread<BC: BlockCache, BV: BlockValidator> {
    chain_controller: ChainController<BC, BV>,
    block_queue: Receiver<BlockWrapper>,
    exit: Arc<AtomicBool>,
}

trait StopHandle: Clone {
    fn stop(&self);
}

impl<BC: BlockCache + 'static, BV: BlockValidator + 'static> ChainThread<BC, BV> {
    fn new(
        chain_controller: ChainController<BC, BV>,
        block_queue: Receiver<BlockWrapper>,
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
            let block = match self
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
                Ok(block) => block,
            };
            self.chain_controller.on_block_received(block)?;

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
