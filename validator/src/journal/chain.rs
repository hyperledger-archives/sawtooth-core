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

use std::fs::File;
use std::io;
use std::io::prelude::*;
use std::marker::Send;
use std::marker::Sync;
use std::path::PathBuf;
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
use journal::block_validator::{BlockValidationResult, BlockValidator, ValidationError};
use journal::block_wrapper::BlockWrapper;
use metrics;

use proto::transaction_receipt::TransactionReceipt;
use scheduler::TxnExecutionResult;

const RECV_TIMEOUT_MILLIS: u64 = 100;

lazy_static! {
    static ref COLLECTOR: metrics::MetricsCollectorHandle =
        metrics::get_collector("sawtooth_validator.chain.ChainController");
}

#[derive(Debug)]
pub enum ChainControllerError {
    QueueRecvError(RecvError),
    ChainIdError(io::Error),
    ChainUpdateError(String),
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

pub trait ChainObserver: Send + Sync {
    fn chain_update(&mut self, block: &BlockWrapper, receipts: &[&TransactionReceipt]);
}

pub trait ExternalLock: Send + Sync {
    fn lock(&self) -> Box<ExternalLockGuard>;
}

pub trait ExternalLockGuard: Drop {
    fn release(&self);
}

pub trait ChainHeadUpdateObserver: Send + Sync {
    /// Called when the chain head has updated.
    ///
    /// Args:
    ///     block: the new chain head
    ///     committed_batches: all of the batches that have been committed
    ///         on the given fork. This may be across multiple blocks.
    ///     uncommitted_batches: all of the batches that have been uncommitted
    ///         from the previous fork, if one was dropped.
    fn on_chain_head_updated(
        &mut self,
        block: BlockWrapper,
        committed_batches: Vec<Batch>,
        uncommitted_batches: Vec<Batch>,
    );
}

pub trait BlockCache: Send + Sync {
    fn contains(&self, block_id: &str) -> bool;

    fn put(&mut self, block: BlockWrapper);

    fn get(&self, block_id: &str) -> Option<BlockWrapper>;
}

#[derive(Debug)]
pub enum ChainReadError {
    GeneralReadError(String),
}

pub trait ChainReader: Send + Sync {
    fn chain_head(&self) -> Result<Option<BlockWrapper>, ChainReadError>;
    fn count_committed_transactions(&self) -> Result<usize, ChainReadError>;
}

pub trait ChainWriter: Send + Sync {
    fn update_chain(
        &mut self,
        new_chain: &[BlockWrapper],
        old_chain: &[BlockWrapper],
    ) -> Result<(), ChainControllerError>;
}

struct ChainControllerState<BC: BlockCache, BV: BlockValidator, CW: ChainWriter> {
    block_cache: BC,
    block_validator: BV,
    chain_writer: CW,
    chain_reader: Box<ChainReader>,
    chain_head_lock: Box<ExternalLock>,
    chain_head: Option<BlockWrapper>,
    chain_id_manager: ChainIdManager,
    chain_head_update_observer: Box<ChainHeadUpdateObserver>,
    observers: Vec<Box<ChainObserver>>,
}

#[derive(Clone)]
pub struct ChainController<BC: BlockCache, BV: BlockValidator, CW: ChainWriter> {
    state: Arc<RwLock<ChainControllerState<BC, BV, CW>>>,
    stop_handle: Arc<Mutex<Option<ChainThreadStopHandle>>>,
    block_queue_sender: Option<Sender<BlockWrapper>>,
    validation_result_sender: Option<Sender<(bool, BlockValidationResult)>>,
}

impl<BC: BlockCache + 'static, BV: BlockValidator + 'static, CW: ChainWriter + 'static>
    ChainController<BC, BV, CW>
{
    pub fn new(
        block_cache: BC,
        block_validator: BV,
        chain_writer: CW,
        chain_reader: Box<ChainReader>,
        chain_head_lock: Box<ExternalLock + 'static>,
        data_dir: String,
        chain_head_update_observer: Box<ChainHeadUpdateObserver>,
        observers: Vec<Box<ChainObserver>>,
    ) -> Self {
        ChainController {
            state: Arc::new(RwLock::new(ChainControllerState {
                block_cache,
                block_validator,
                chain_writer,
                chain_reader,
                chain_head_lock,
                chain_id_manager: ChainIdManager::new(data_dir),
                chain_head_update_observer,
                observers,
                chain_head: None,
            })),
            stop_handle: Arc::new(Mutex::new(None)),
            block_queue_sender: None,
            validation_result_sender: None,
        }
    }

    pub fn chain_head(&self) -> Option<BlockWrapper> {
        let state = self.state
            .read()
            .expect("No lock holder should have poisoned the lock");

        state.chain_head.clone()
    }

    pub fn on_block_received(&mut self, block: BlockWrapper) -> Result<(), ChainControllerError> {
        let mut state = self.state
            .write()
            .expect("No lock holder should have poisoned the lock");

        if has_block_no_lock(&state, block.header_signature()) {
            return Ok(());
        }

        if state.chain_head.is_none() {
            if let Err(err) = set_genesis(&mut state, block.clone()) {
                warn!(
                    "Unable to set chain head; genesis block {} is not valid: {:?}",
                    block.header_signature(),
                    err
                );
            }
            return Ok(());
        }

        state.block_cache.put(block.clone());
        self.submit_blocks_for_verification(&state.block_validator, &[block])?;
        Ok(())
    }

    pub fn has_block(&self, block_id: &str) -> bool {
        let state = self.state
            .read()
            .expect("No lock holder should have poisoned the lock");
        has_block_no_lock(&state, block_id)
    }

    fn on_block_validated(&mut self, commit_new_block: bool, result: BlockValidationResult) {
        let mut state = self.state
            .write()
            .expect("No lock holder should have poisoned the lock");

        let mut blocks_considered_count = COLLECTOR.counter("blocks_considered_count", None, None);
        blocks_considered_count.inc();

        let new_block = result.block;
        let initial_chain_head = result.chain_head.header_signature().clone();
        if state
            .chain_head
            .as_ref()
            .map(|block| initial_chain_head != block.header_signature())
            .unwrap_or(false)
        {
            info!(
                "Chain head updated from {} to {} while processing block {}",
                result.chain_head,
                state.chain_head.as_ref().unwrap(),
                new_block
            );
            if let Err(err) =
                self.submit_blocks_for_verification(&state.block_validator, &[new_block])
            {
                error!("Unable to submit block for verification: {:?}", err);
            }
        } else if commit_new_block {
            let _chain_head_guard = state.chain_head_lock.lock();
            let chain_head_block = new_block.clone();
            state.chain_head = Some(new_block);

            if let Err(err) = state
                .chain_writer
                .update_chain(&result.new_chain, &result.current_chain)
            {
                error!("Unable to update chain {:?}", err);
                return;
            }

            info!(
                "Chain head updated to {}",
                state.chain_head.as_ref().unwrap()
            );

            let mut chain_head_gauge = COLLECTOR.gauge("chain_head", None, None);
            chain_head_gauge.set_value(&chain_head_block.header_signature()[0..8]);

            let mut committed_transactions_count =
                COLLECTOR.counter("committed_transactions_count", None, None);
            committed_transactions_count.inc_n(result.transaction_count);

            let mut block_num_guage = COLLECTOR.gauge("block_num", None, None);
            block_num_guage.set_value(chain_head_block.block_num());

            let chain_head = state.chain_head.clone().unwrap();
            notify_on_chain_updated(
                &mut state,
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

            let mut new_chain = result.new_chain;
            new_chain.reverse();

            for block in new_chain {
                let receipts: Vec<TransactionReceipt> = block
                    .execution_results
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
                COLLECTOR.gauge("committed_transactions_gauge", None, None);
            committed_transactions_gauge.set_value(total_committed_txns);
        } else {
            info!("Rejected new chain head: {}", new_block);
        }
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
            validation_result_sender: self.validation_result_sender.clone(),
        }
    }

    fn submit_blocks_for_verification(
        &self,
        block_validator: &BV,
        blocks: &[BlockWrapper],
    ) -> Result<(), ChainControllerError> {
        let sender = self.validation_result_sender
            .as_ref()
            .expect(
                "Attempted to submit blocks for validation before starting the chain controller",
            )
            .clone();
        block_validator.submit_blocks_for_verification(blocks, sender);
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

    pub fn start(&mut self) {
        let mut stop_handle = self.stop_handle.lock().unwrap();
        if stop_handle.is_none() {
            {
                // we need to check to see if a genesis block was created and stored,
                // before this controller was started
                let mut state = self.state
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
                    let mut gauge = COLLECTOR.gauge("chain_head", None, None);
                    gauge.set_value(&notify_block.header_signature()[0..8]);
                    notify_on_chain_updated(&mut state, notify_block, vec![], vec![]);
                }
            }

            let (block_queue_sender, block_queue_receiver) = channel();
            let (validation_result_sender, validation_result_receiver) = channel();

            self.block_queue_sender = Some(block_queue_sender);
            self.validation_result_sender = Some(validation_result_sender);

            let thread_chain_controller = self.light_clone();
            let exit_flag = Arc::new(AtomicBool::new(false));
            let mut chain_thread = ChainThread::new(
                thread_chain_controller,
                block_queue_receiver,
                exit_flag.clone(),
            );
            *stop_handle = Some(ChainThreadStopHandle::new(exit_flag.clone()));
            let chain_thread_builder =
                thread::Builder::new().name("ChainThread:BlockRecevier".into());
            chain_thread_builder
                .spawn(move || {
                    if let Err(err) = chain_thread.run() {
                        error!("Error occurred during ChainController loop: {:?}", err);
                    }
                })
                .unwrap();
            let result_thread_builder =
                thread::Builder::new().name("ChainThread:ValidationResultRecevier".into());
            let mut result_thread_controller = self.light_clone();
            let result_thread_exit = exit_flag.clone();
            result_thread_builder
                .spawn(move || loop {
                    let (can_commit, result) = match validation_result_receiver
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
                        result_thread_controller.on_block_validated(can_commit, result);
                    } else {
                        break;
                    }
                })
                .unwrap();
        }
    }

    pub fn stop(&mut self) {
        let mut stop_handle = self.stop_handle.lock().unwrap();
        if stop_handle.is_some() {
            let handle: ChainThreadStopHandle = stop_handle.take().unwrap();
            handle.stop();
        }
    }
}

fn has_block_no_lock<BC: BlockCache, BV: BlockValidator, CW: ChainWriter>(
    state: &ChainControllerState<BC, BV, CW>,
    block_id: &str,
) -> bool {
    state.block_cache.contains(block_id) || state.block_validator.in_process(block_id)
        || state.block_validator.in_pending(block_id)
}

/// This is used by a non-genesis journal when it has received the
/// genesis block from the genesis validator
fn set_genesis<BC: BlockCache, BV: BlockValidator, CW: ChainWriter>(
    state: &mut ChainControllerState<BC, BV, CW>,
    block: BlockWrapper,
) -> Result<(), ChainControllerError> {
    if block.previous_block_id() == journal::NULL_BLOCK_IDENTIFIER {
        let chain_id = state.chain_id_manager.get_block_chain_id()?;
        if chain_id
            .as_ref()
            .map(|block_id| block_id != block.header_signature())
            .unwrap_or(false)
        {
            warn!(
                "Block id does not match block chain id {}. Ignoring initial chain head: {}",
                chain_id.unwrap(),
                block.header_signature()
            );
        } else {
            state.block_validator.validate_block(block.clone())?;

            if chain_id.is_none() {
                state
                    .chain_id_manager
                    .save_block_chain_id(block.header_signature())?;
            }

            state.chain_writer.update_chain(&[block.clone()], &[])?;
            state.chain_head = Some(block.clone());
            notify_on_chain_updated(state, block.clone(), vec![], vec![]);
        }
    }

    Ok(())
}

fn notify_on_chain_updated<BC: BlockCache, BV: BlockValidator, CW: ChainWriter>(
    state: &mut ChainControllerState<BC, BV, CW>,
    block: BlockWrapper,
    committed_batches: Vec<Batch>,
    uncommitted_batches: Vec<Batch>,
) {
    state.chain_head_update_observer.on_chain_head_updated(
        block,
        committed_batches,
        uncommitted_batches,
    );
}

impl<'a> From<&'a TxnExecutionResult> for TransactionReceipt {
    fn from(result: &'a TxnExecutionResult) -> Self {
        let mut receipt = TransactionReceipt::new();

        receipt.set_data(protobuf::RepeatedField::from_vec(
            result.data.iter().map(|(_, data)| data.clone()).collect(),
        ));
        receipt.set_state_changes(protobuf::RepeatedField::from_vec(
            result.state_changes.clone(),
        ));
        receipt.set_events(protobuf::RepeatedField::from_vec(result.events.clone()));
        receipt.set_transaction_id(result.signature.clone());

        receipt
    }
}

struct ChainThread<BC: BlockCache, BV: BlockValidator, CW: ChainWriter> {
    chain_controller: ChainController<BC, BV, CW>,
    block_queue: Receiver<BlockWrapper>,
    exit: Arc<AtomicBool>,
}

trait StopHandle: Clone {
    fn stop(&self);
}

impl<BC: BlockCache + 'static, BV: BlockValidator + 'static, CW: ChainWriter + 'static>
    ChainThread<BC, BV, CW>
{
    fn new(
        chain_controller: ChainController<BC, BV, CW>,
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
            let block = match self.block_queue
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

/// The ChainIdManager is in charge of of keeping track of the block-chain-id
/// stored in the data_dir.
#[derive(Clone, Debug)]
struct ChainIdManager {
    data_dir: String,
}

impl ChainIdManager {
    pub fn new(data_dir: String) -> Self {
        ChainIdManager { data_dir }
    }

    pub fn save_block_chain_id(&self, block_chain_id: &str) -> Result<(), io::Error> {
        let mut path = PathBuf::new();
        path.push(&self.data_dir);
        path.push("block-chain-id");

        let mut file = File::create(path)?;
        file.write_all(block_chain_id.as_bytes())
    }

    pub fn get_block_chain_id(&self) -> Result<Option<String>, io::Error> {
        let mut path = PathBuf::new();
        path.push(&self.data_dir);
        path.push("block-chain-id");

        match File::open(path) {
            Ok(mut file) => {
                let mut contents = String::new();
                file.read_to_string(&mut contents)?;
                Ok(Some(contents))
            }
            Err(ref err) if err.kind() == io::ErrorKind::NotFound => Ok(None),
            Err(err) => Err(err),
        }
    }
}

#[cfg(tests)]
mod tests {}
