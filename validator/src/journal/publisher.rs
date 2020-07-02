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
// allow borrowed box, this is required to use PublisherState trait
#![allow(clippy::borrowed_box)]

use cpython::{NoArgs, ObjectProtocol, PyClone, PyDict, PyList, PyObject, Python};
use std::collections::{HashMap, HashSet};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::{channel, Receiver, RecvTimeoutError, SendError, Sender};
use std::sync::{Arc, RwLock};
use std::thread;
use std::time::Duration;

use sawtooth::journal::{
    block_manager::{BlockManager, BlockRef},
    candidate_block::{CandidateBlock, CandidateBlockError},
    chain_commit_state::TransactionCommitCache,
    chain_head_lock::ChainHeadLock,
    commit_store::CommitStore,
    publisher::{
        BatchObserver, FinalizeBlockError, InitializeBlockError, PendingBatchesPool,
        PublisherState, SyncPublisher,
    },
};
use sawtooth::state::{settings_view::SettingsView, state_view_factory::StateViewFactory};
use sawtooth::{batch::Batch, block::Block, execution::execution_platform::ExecutionPlatform};

use ffi::py_import_class;
use journal::candidate_block::FFICandidateBlock;
use py_object_wrapper::PyObjectWrapper;

const NUM_PUBLISH_COUNT_SAMPLES: usize = 5;
const INITIAL_PUBLISH_COUNT: usize = 30;

lazy_static! {
    static ref PY_BLOCK_HEADER_CLASS: PyObject =
        py_import_class("sawtooth_validator.protobuf.block_pb2", "BlockHeader");
    static ref PY_BLOCK_BUILDER_CLASS: PyObject =
        py_import_class("sawtooth_validator.journal.block_builder", "BlockBuilder");
}

#[derive(Debug)]
pub enum CancelBlockError {
    BlockNotInitialized,
}

#[derive(Debug)]
pub enum BlockPublisherError {
    UnknownBlock(String),
}

pub struct BlockPublisherState {
    pub transaction_executor: Box<dyn ExecutionPlatform>,
    pub batch_observers: Vec<Box<dyn BatchObserver>>,
    pub chain_head: Option<Block>,
    pub candidate_block: Option<Box<dyn CandidateBlock>>,
    pub pending_batches: PendingBatchesPool,
    block_references: HashMap<String, BlockRef>,
}

impl BlockPublisherState {
    pub fn new(
        transaction_executor: Box<dyn ExecutionPlatform>,
        batch_observers: Vec<Box<dyn BatchObserver>>,
        chain_head: Option<Block>,
        candidate_block: Option<Box<dyn CandidateBlock>>,
        pending_batches: PendingBatchesPool,
    ) -> Self {
        BlockPublisherState {
            batch_observers,
            transaction_executor,
            chain_head,
            candidate_block,
            pending_batches,
            block_references: HashMap::new(),
        }
    }
}

impl PublisherState for BlockPublisherState {
    fn pending_batches(&self) -> &PendingBatchesPool {
        &self.pending_batches
    }

    fn mut_pending_batches(&mut self) -> &mut PendingBatchesPool {
        &mut self.pending_batches
    }

    fn chain_head(&mut self, block: Option<Block>) {
        self.chain_head = block;
    }

    fn candidate_block(&mut self) -> &mut Option<Box<dyn CandidateBlock>> {
        &mut self.candidate_block
    }

    fn set_candidate_block(
        &mut self,
        candidate_block: Option<Box<dyn CandidateBlock>>,
    ) -> Option<Box<dyn CandidateBlock>> {
        let old_candidate_block = self.candidate_block.take();
        self.candidate_block = candidate_block;
        old_candidate_block
    }

    fn block_references(&mut self) -> &mut HashMap<String, BlockRef> {
        &mut self.block_references
    }

    fn batch_observers(&self) -> &[Box<dyn BatchObserver>] {
        &self.batch_observers
    }

    fn transaction_executor(&self) -> &Box<dyn ExecutionPlatform> {
        &self.transaction_executor
    }
}

pub struct SyncBlockPublisher {
    state: Arc<RwLock<Box<dyn PublisherState>>>,

    commit_store: CommitStore,
    block_manager: BlockManager,
    batch_injector_factory: PyObject,
    state_view_factory: StateViewFactory,
    block_sender: PyObject,
    batch_publisher: PyObject,
    identity_signer: PyObject,
    data_dir: PyObject,
    config_dir: PyObject,
    permission_verifier: PyObject,

    exit: Arc<Exit>,
}

impl Clone for SyncBlockPublisher {
    fn clone(&self) -> Self {
        let state = Arc::clone(&self.state);

        let gil = Python::acquire_gil();
        let py = gil.python();

        SyncBlockPublisher {
            state,
            commit_store: self.commit_store.clone(),
            block_manager: self.block_manager.clone(),
            batch_injector_factory: self.batch_injector_factory.clone_ref(py),
            state_view_factory: self.state_view_factory.clone(),
            block_sender: self.block_sender.clone_ref(py),
            batch_publisher: self.batch_publisher.clone_ref(py),
            identity_signer: self.identity_signer.clone_ref(py),
            data_dir: self.data_dir.clone_ref(py),
            config_dir: self.config_dir.clone_ref(py),
            permission_verifier: self.permission_verifier.clone_ref(py),
            exit: Arc::clone(&self.exit),
        }
    }
}

impl SyncPublisher for SyncBlockPublisher {
    fn box_clone(&self) -> Box<dyn SyncPublisher> {
        Box::new(self.clone())
    }

    fn state(&self) -> &Arc<RwLock<Box<dyn PublisherState>>> {
        &self.state
    }

    fn on_chain_updated(
        &self,
        state: &mut Box<dyn PublisherState>,
        chain_head: Block,
        committed_batches: Vec<Batch>,
        uncommitted_batches: Vec<Batch>,
    ) {
        info!("Now building on top of block, {}", chain_head);
        let batches_len = chain_head.batches.len();
        state.chain_head(Some(chain_head));
        let mut previous_block_option = None;
        if let (true, Some(previous_block)) = self.is_building_block(state) {
            previous_block_option = Some(previous_block);
            self.cancel_block(state, false);
        }

        state.mut_pending_batches().update_limit(batches_len);
        state
            .mut_pending_batches()
            .rebuild(Some(committed_batches), Some(uncommitted_batches));

        if let Some(previous_block) = previous_block_option {
            if let Err(err) = self.initialize_block(state, &previous_block, false) {
                error!("Unable to initialize block after canceling: {:?}", err);
            }
        }
    }

    fn on_chain_updated_internal(
        &mut self,
        chain_head: Block,
        committed_batches: Vec<Batch>,
        uncommitted_batches: Vec<Batch>,
    ) {
        let mut state = self
            .state
            .write()
            .expect("RwLock was poisoned during a write lock");
        self.on_chain_updated(
            &mut state,
            chain_head,
            committed_batches,
            uncommitted_batches,
        );
    }

    fn on_batch_received(&self, batch: Batch) {
        let mut state = self.state.write().expect("Lock should not be poisoned");

        // Batch can be added if the signer is authorized and the batch isn't already committed
        let permission_check = {
            let gil = Python::acquire_gil();
            let py = gil.python();

            let batch_wrapper = PyObjectWrapper::from(batch.clone());

            self.permission_verifier
                .call_method(py, "is_batch_signer_authorized", (batch_wrapper,), None)
                .expect("PermissionVerifier has no method is_batch_signer_authorized")
                .extract(py)
                .expect("PermissionVerifier.is_batch_signer_authorized did not return bool")
        };

        let batch_already_committed = self
            .commit_store
            .contains_batch(batch.header_signature.as_str())
            .expect("Couldn't check for batch");

        if permission_check && !batch_already_committed {
            // If the batch is already in the pending queue, don't do anything further
            if state.mut_pending_batches().append(batch.clone()) {
                // Notify observers
                for observer in state.batch_observers() {
                    observer.notify_batch_pending(&batch);
                }
                // If currently building a block, add the batch to it
                if let Some(ref mut candidate_block) = state.candidate_block() {
                    if candidate_block.can_add_batch() {
                        candidate_block.add_batch(batch);
                    }
                }
            }
        }
    }

    fn cancel_block(&self, state: &mut Box<dyn PublisherState>, unref_block: bool) {
        let mut candidate_block = None;
        candidate_block = state.set_candidate_block(candidate_block);
        if let Some(mut candidate_block) = candidate_block {
            if unref_block {
                // Drop Ref-D: We cancelled the block, so we can drop the ext. ref. to its predecessor.
                if state
                    .block_references()
                    .remove(&candidate_block.previous_block_id())
                    .is_none()
                {
                    error!(
                        "Reference not found for canceled block {}",
                        &candidate_block.previous_block_id()
                    );
                }
            }
            candidate_block.cancel();
        }
    }

    fn initialize_block(
        &self,
        state: &mut Box<dyn PublisherState>,
        previous_block: &Block,
        ref_block: bool,
    ) -> Result<(), InitializeBlockError> {
        if state.candidate_block().is_some() {
            warn!("Tried to initialize block but block already initialized");
            return Err(InitializeBlockError::BlockInProgress);
        }

        if ref_block {
            // Create Ref-D: Hold the predecessor until we are done building the new block. This ext.
            // ref. must be dropped either 1) after the block is finalized but before sending the block
            // to the completer or 2) after the block is cancelled.
            match self
                .block_manager
                .ref_block(&previous_block.header_signature)
            {
                Ok(block_ref) => {
                    state
                        .block_references()
                        .insert(block_ref.block_id().to_owned(), block_ref);
                }
                Err(err) => {
                    error!("Unable to ref block! {}: {:?}", &previous_block, err);
                    return Err(InitializeBlockError::MissingPredecessor);
                }
            }
        }
        let mut candidate_block = {
            let settings_view: SettingsView = self
                .state_view_factory
                .create_view(&previous_block.state_root_hash)
                .expect("Failed to get state view for previous block");

            let max_batches = settings_view
                .get_setting_u32("sawtooth.publisher.max_batches_per_block", Some(0u32))
                .expect("Unable to get value from settings view")
                .expect("Failed to return expected default") as usize;

            let gil = Python::acquire_gil();
            let py = gil.python();

            let public_key = self.get_public_key(py);
            let batch_injectors = self.load_injectors(py, &previous_block.state_root_hash);

            let kwargs = PyDict::new(py);
            kwargs
                .set_item(py, "block_num", previous_block.block_num + 1)
                .unwrap();
            kwargs
                .set_item(py, "previous_block_id", &previous_block.header_signature)
                .unwrap();
            kwargs
                .set_item(py, "signer_public_key", &public_key)
                .unwrap();
            let block_header = PY_BLOCK_HEADER_CLASS
                .call(py, NoArgs, Some(&kwargs))
                .expect("BlockHeader could not be constructed");

            let block_builder = PY_BLOCK_BUILDER_CLASS
                .call(py, (block_header,), None)
                .expect("BlockBuilder could not be constructed");

            let scheduler = state
                .transaction_executor()
                .create_scheduler(&previous_block.state_root_hash)
                .expect("Failed to create new scheduler");

            let committed_txn_cache = TransactionCommitCache::new(self.commit_store.clone());

            FFICandidateBlock::new(
                previous_block.clone(),
                self.commit_store.clone(),
                scheduler,
                committed_txn_cache,
                block_builder,
                max_batches,
                batch_injectors,
                self.identity_signer.clone_ref(py),
                settings_view,
            )
        };

        for batch in state.pending_batches().iter() {
            if candidate_block.can_add_batch() {
                candidate_block.add_batch(batch.clone());
            } else {
                break;
            }
        }
        state.set_candidate_block(Some(Box::new(candidate_block)));

        Ok(())
    }

    fn finalize_block(
        &self,
        state: &mut Box<dyn PublisherState>,
        consensus_data: &[u8],
        force: bool,
    ) -> Result<String, FinalizeBlockError> {
        let mut option_result = None;
        if let Some(ref mut candidate_block) = &mut state.candidate_block() {
            option_result = Some(candidate_block.finalize(consensus_data, force));
        }

        let res = match option_result {
            Some(result) => match result {
                Ok(finalize_result) => {
                    state.mut_pending_batches().update(
                        finalize_result.remaining_batches.clone(),
                        &finalize_result.last_batch,
                    );

                    let previous_block_id = &state
                        .candidate_block()
                        .as_ref()
                        .expect("Failed to get candidate block, even though it is being published!")
                        .previous_block_id();

                    state.set_candidate_block(None);
                    match finalize_result.block {
                        Some(block) => {
                            // Drop Ref-D: We have finished creating this block and are about to
                            // send it to the completer, so we can drop the ext. ref. to its
                            // predecessor.
                            if state.block_references().remove(previous_block_id).is_none() {
                                error!(
                                    "Reference not found for finalized block {}",
                                    previous_block_id
                                );
                            }

                            Some(Ok(
                                self.publish_block(block, finalize_result.injected_batch_ids)
                            ))
                        }
                        None => None,
                    }
                }
                Err(CandidateBlockError::BlockEmpty) => Some(Err(FinalizeBlockError::BlockEmpty)),
            },
            None => Some(Err(FinalizeBlockError::BlockNotInitialized)),
        };
        if let Some(val) = res {
            val
        } else {
            self.restart_block(state);
            Err(FinalizeBlockError::BlockEmpty)
        }
    }

    fn summarize_block(
        &self,
        state: &mut Box<dyn PublisherState>,
        force: bool,
    ) -> Result<Vec<u8>, FinalizeBlockError> {
        let result = match state.candidate_block() {
            None => Some(Err(FinalizeBlockError::BlockNotInitialized)),
            Some(ref mut candidate_block) => match candidate_block.summarize(force) {
                Ok(summary) => {
                    if let Some(s) = summary {
                        Some(Ok(s))
                    } else {
                        None
                    }
                }
                Err(CandidateBlockError::BlockEmpty) => Some(Err(FinalizeBlockError::BlockEmpty)),
            },
        };
        if let Some(res) = result {
            res
        } else {
            self.restart_block(state);
            Err(FinalizeBlockError::BlockEmpty)
        }
    }

    fn stopped(&self) -> bool {
        self.exit.get()
    }

    fn stop(&self) {
        self.exit.set()
    }
}

impl SyncBlockPublisher {
    fn load_injectors(&self, py: Python, state_root: &str) -> Vec<PyObject> {
        self.batch_injector_factory
            .call_method(py, "create_injectors", (state_root,), None)
            .expect("BatchInjectorFactory has no method 'create_injectors'")
            .extract::<PyList>(py)
            .unwrap()
            .iter(py)
            .collect()
    }

    fn get_block(&self, block_id: &str) -> Result<Block, BlockPublisherError> {
        self.block_manager
            .get(&[block_id])
            .next()
            .expect("Did not return any Results, even not found blocks")
            .ok_or_else(|| BlockPublisherError::UnknownBlock(block_id.to_string()))
    }

    fn restart_block(&self, state: &mut Box<dyn PublisherState>) {
        if let Some(previous_block) = state.candidate_block().as_ref().map(|candidate| {
            self.get_block(&candidate.previous_block_id())
                .expect("Failed to get previous block, but we are building on it.")
        }) {
            self.cancel_block(state, false);

            if let Err(err) = self.initialize_block(state, &previous_block, false) {
                error!("Initialization failed unexpectedly: {:?}", err);
            }
        }
    }

    fn publish_block(&self, block: Block, injected_batches: Vec<String>) -> String {
        let gil = Python::acquire_gil();
        let py = gil.python();

        let wrapper = PyObjectWrapper::from(block);

        self.block_sender
            .call_method(py, "send", (&wrapper, injected_batches), None)
            .map_err(|py_err| {
                ::pylogger::exception(py, "{:?}", py_err);
            })
            .expect("BlockSender.send() raised an exception");

        let block: Block = Block::from(wrapper);
        let block_id = block.header_signature;
        counter!("publisher.BlockPublisher.blocks_published_count", 1);

        block_id
    }

    fn get_public_key(&self, py: Python) -> String {
        self.identity_signer
            .call_method(py, "get_public_key", NoArgs, None)
            .expect("IdentitySigner has no method get_public_key")
            .call_method(py, "as_hex", NoArgs, None)
            .expect("PublicKey object as no method as_hex")
            .extract::<String>(py)
            .unwrap()
    }

    fn is_building_block(&self, state: &mut Box<dyn PublisherState>) -> (bool, Option<Block>) {
        if let Some(ref candidate_block) = state.candidate_block() {
            let previous = self
                .get_block(&candidate_block.previous_block_id())
                .expect("Failed to get block being built on");
            (true, Some(previous))
        } else {
            (false, None)
        }
    }
}

#[derive(Clone)]
pub struct BlockPublisher {
    pub publisher: Box<dyn SyncPublisher>,
}

impl BlockPublisher {
    #![allow(clippy::too_many_arguments)]
    pub fn new(
        commit_store: CommitStore,
        block_manager: BlockManager,
        transaction_executor: Box<dyn ExecutionPlatform>,
        state_view_factory: StateViewFactory,
        block_sender: PyObject,
        batch_publisher: PyObject,
        chain_head: Option<Block>,
        identity_signer: PyObject,
        data_dir: PyObject,
        config_dir: PyObject,
        permission_verifier: PyObject,
        batch_observers: Vec<Box<dyn BatchObserver>>,
        batch_injector_factory: PyObject,
    ) -> Self {
        let state: Arc<RwLock<Box<dyn PublisherState>>> =
            Arc::new(RwLock::new(Box::new(BlockPublisherState::new(
                transaction_executor,
                batch_observers,
                chain_head,
                None,
                PendingBatchesPool::new(NUM_PUBLISH_COUNT_SAMPLES, INITIAL_PUBLISH_COUNT),
            ))));

        let publisher = SyncBlockPublisher {
            state,
            commit_store,
            block_manager,
            state_view_factory,
            block_sender,
            batch_publisher,
            identity_signer,
            data_dir,
            config_dir,
            permission_verifier,
            batch_injector_factory,
            exit: Arc::new(Exit::new()),
        };

        BlockPublisher {
            publisher: Box::new(publisher),
        }
    }

    pub fn start(&mut self) -> IncomingBatchSender {
        let (batch_tx, mut batch_rx) = make_batch_queue();
        let builder = thread::Builder::new().name("PublisherThread".into());
        let block_publisher = self.publisher.clone();
        builder
            .spawn(move || {
                loop {
                    // Receive and process a batch
                    match batch_rx.get(Duration::from_millis(100)) {
                        Err(err) => match err {
                            BatchQueueError::Timeout => {
                                if block_publisher.stopped() {
                                    break;
                                }
                            }
                            err => panic!("Unhandled error: {:?}", err),
                        },
                        Ok(batch) => {
                            block_publisher.on_batch_received(batch);
                        }
                    }
                }
                warn!("PublisherThread exiting");
            })
            .unwrap();

        batch_tx
    }

    pub fn cancel_block(&self) -> Result<(), CancelBlockError> {
        let mut state = self.publisher.state().write().expect("RwLock was poisoned");
        if state.candidate_block().is_some() {
            self.publisher.cancel_block(&mut state, true);
            Ok(())
        } else {
            Err(CancelBlockError::BlockNotInitialized)
        }
    }

    pub fn stop(&self) {
        self.publisher.stop();
    }

    pub fn chain_head_lock(&self) -> ChainHeadLock {
        ChainHeadLock::new(self.publisher.clone())
    }

    pub fn initialize_block(&self, previous_block: &Block) -> Result<(), InitializeBlockError> {
        let mut state = self.publisher.state().write().expect("RwLock was poisoned");
        self.publisher
            .initialize_block(&mut state, previous_block, true)
    }

    pub fn finalize_block(
        &self,
        consensus_data: &[u8],
        force: bool,
    ) -> Result<String, FinalizeBlockError> {
        let mut state = self.publisher.state().write().expect("RwLock is poisoned");
        self.publisher
            .finalize_block(&mut state, consensus_data, force)
    }

    pub fn summarize_block(&self, force: bool) -> Result<Vec<u8>, FinalizeBlockError> {
        let mut state = self.publisher.state().write().expect("RwLock is poisoned");
        self.publisher.summarize_block(&mut state, force)
    }

    pub fn pending_batch_info(&self) -> (i32, i32) {
        let state = self
            .publisher
            .state()
            .read()
            .expect("RwLock was poisoned during a write lock");
        (
            state.pending_batches().len() as i32,
            state.pending_batches().limit() as i32,
        )
    }

    pub fn has_batch(&self, batch_id: &str) -> bool {
        let state = self
            .publisher
            .state()
            .read()
            .expect("RwLock was poisoned during a write lock");
        state.pending_batches().contains(batch_id)
    }
}

/// This queue keeps track of the batch ids so that components on the edge
/// can filter out duplicates early. However, there is still an opportunity for
/// duplicates to make it into this queue, which is intentional to avoid
/// blocking threads trying to put/get from the queue. Any duplicates
/// introduced by this must be filtered out later.
pub fn make_batch_queue() -> (IncomingBatchSender, IncomingBatchReceiver) {
    let (sender, reciever) = channel();
    let ids = Arc::new(RwLock::new(HashSet::new()));
    (
        IncomingBatchSender::new(ids.clone(), sender),
        IncomingBatchReceiver::new(ids, reciever),
    )
}

pub struct IncomingBatchReceiver {
    ids: Arc<RwLock<HashSet<String>>>,
    receiver: Receiver<Batch>,
}

impl IncomingBatchReceiver {
    pub fn new(
        ids: Arc<RwLock<HashSet<String>>>,
        receiver: Receiver<Batch>,
    ) -> IncomingBatchReceiver {
        IncomingBatchReceiver { ids, receiver }
    }

    pub fn get(&mut self, timeout: Duration) -> Result<Batch, BatchQueueError> {
        let batch = self.receiver.recv_timeout(timeout)?;
        self.ids
            .write()
            .expect("RwLock was poisoned during a write lock")
            .remove(&batch.header_signature);
        Ok(batch)
    }
}

#[derive(Clone)]
pub struct IncomingBatchSender {
    ids: Arc<RwLock<HashSet<String>>>,
    sender: Sender<Batch>,
}

impl IncomingBatchSender {
    pub fn new(ids: Arc<RwLock<HashSet<String>>>, sender: Sender<Batch>) -> IncomingBatchSender {
        IncomingBatchSender { ids, sender }
    }
    pub fn put(&mut self, batch: Batch) -> Result<(), BatchQueueError> {
        let mut ids = self
            .ids
            .write()
            .expect("RwLock was poisoned during a write lock");

        if !ids.contains(&batch.header_signature) {
            ids.insert(batch.header_signature.clone());
            self.sender.send(batch).map_err(BatchQueueError::from)
        } else {
            Ok(())
        }
    }

    pub fn has_batch(&self, batch_id: &str) -> Result<bool, BatchQueueError> {
        Ok(self
            .ids
            .read()
            .expect("RwLock was poisoned during a write lock")
            .contains(batch_id))
    }
}

#[derive(Debug)]
pub enum BatchQueueError {
    SenderError(SendError<Batch>),
    Timeout,
}

impl From<SendError<Batch>> for BatchQueueError {
    fn from(e: SendError<Batch>) -> Self {
        BatchQueueError::SenderError(e)
    }
}

impl From<RecvTimeoutError> for BatchQueueError {
    fn from(_: RecvTimeoutError) -> Self {
        BatchQueueError::Timeout
    }
}

/// Utility class for signaling that a background thread should shutdown
#[derive(Default)]
pub struct Exit {
    flag: AtomicBool,
}

impl Exit {
    pub fn new() -> Self {
        Exit {
            flag: AtomicBool::new(false),
        }
    }

    pub fn get(&self) -> bool {
        self.flag.load(Ordering::Relaxed)
    }

    pub fn set(&self) {
        self.flag.store(true, Ordering::Relaxed);
    }
}
