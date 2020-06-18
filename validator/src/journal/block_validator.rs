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

use batch::Batch;
use block::Block;
use execution::execution_platform::{ExecutionPlatform, NULL_STATE_HASH};
use gossip::permission_verifier::PermissionVerifier;
use journal::block_scheduler::BlockScheduler;
use journal::chain_commit_state::{
    validate_no_duplicate_batches, validate_no_duplicate_transactions,
    validate_transaction_dependencies, ChainCommitStateError,
};
use journal::validation_rule_enforcer::enforce_validation_rules;
use journal::{block_manager::BlockManager, block_wrapper::BlockStatus};
use scheduler::TxnExecutionResult;
use state::{settings_view::SettingsView, state_view_factory::StateViewFactory};
use std::sync::{
    atomic::{AtomicBool, AtomicUsize, Ordering},
    mpsc::{channel, Receiver, RecvTimeoutError, Sender},
    Arc, Mutex,
};
use std::thread;
use std::time::Duration;
use uluru;

const BLOCKVALIDATION_QUEUE_RECV_TIMEOUT: u64 = 100;

const BLOCK_VALIDATOR_THREAD_NUM: u64 = 2;

const BLOCK_VALIDATION_RESULT_CACHE_SIZE: usize = 512;

#[derive(Debug, Clone, PartialEq)]
pub enum ValidationError {
    BlockValidationFailure(String),
    BlockValidationError(String),
    BlockStoreUpdated,
}

type BlockValidationResultCache =
    uluru::LRUCache<[uluru::Entry<BlockValidationResult>; BLOCK_VALIDATION_RESULT_CACHE_SIZE]>;

#[derive(Clone, Default)]
pub struct BlockValidationResultStore {
    validation_result_cache: Arc<Mutex<BlockValidationResultCache>>,
}

impl BlockValidationResultStore {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn insert(&self, result: BlockValidationResult) {
        self.validation_result_cache
            .lock()
            .expect("The mutex is poisoned")
            .insert(result)
    }

    pub fn get(&self, block_id: &str) -> Option<BlockValidationResult> {
        self.validation_result_cache
            .lock()
            .expect("The mutex is poisoned")
            .find(|r| r.block_id == block_id)
            .cloned()
    }

    pub fn fail_block(&self, block_id: &str) {
        if let Some(ref mut result) = self
            .validation_result_cache
            .lock()
            .expect("The mutex is poisoned")
            .find(|r| r.block_id == block_id)
        {
            result.status = BlockStatus::Invalid
        }
    }
}

impl BlockStatusStore for BlockValidationResultStore {
    fn status(&self, block_id: &str) -> BlockStatus {
        self.validation_result_cache
            .lock()
            .expect("The mutex is poisoned")
            .find(|r| r.block_id == block_id)
            .map(|r| r.status.clone())
            .unwrap_or(BlockStatus::Unknown)
    }
}

impl From<ChainCommitStateError> for ValidationError {
    fn from(other: ChainCommitStateError) -> Self {
        match other {
            ChainCommitStateError::DuplicateBatch(ref batch_id) => {
                ValidationError::BlockValidationFailure(format!(
                    "Validation failure, duplicate batch {}",
                    batch_id
                ))
            }
            ChainCommitStateError::DuplicateTransaction(ref txn_id) => {
                ValidationError::BlockValidationFailure(format!(
                    "Validation failure, duplicate transaction {}",
                    txn_id
                ))
            }
            ChainCommitStateError::MissingDependency(ref txn_id) => {
                ValidationError::BlockValidationFailure(format!(
                    "Validation failure, missing dependency {}",
                    txn_id
                ))
            }
            ChainCommitStateError::Error(reason) => ValidationError::BlockValidationError(reason),
            ChainCommitStateError::BlockStoreUpdated => ValidationError::BlockStoreUpdated,
        }
    }
}

pub trait BlockStatusStore: Clone + Send + Sync {
    fn status(&self, block_id: &str) -> BlockStatus;
}

#[derive(Clone, Debug)]
pub struct BlockValidationResult {
    pub block_id: String,
    pub execution_results: Vec<TxnExecutionResult>,
    pub num_transactions: u64,
    pub status: BlockStatus,
}

impl BlockValidationResult {
    #[allow(dead_code)]
    fn new(
        block_id: String,
        execution_results: Vec<TxnExecutionResult>,
        num_transactions: u64,
        status: BlockStatus,
    ) -> Self {
        BlockValidationResult {
            block_id,
            execution_results,
            num_transactions,
            status,
        }
    }
}

type InternalSender = Sender<(Block, Sender<BlockValidationResult>)>;
type InternalReceiver = Receiver<(Block, Sender<BlockValidationResult>)>;

pub struct BlockValidator<TEP: ExecutionPlatform, PV: PermissionVerifier> {
    channels: Vec<(InternalSender, Option<InternalReceiver>)>,
    index: Arc<AtomicUsize>,
    validation_thread_exit: Arc<AtomicBool>,
    block_scheduler: BlockScheduler<BlockValidationResultStore>,
    block_status_store: BlockValidationResultStore,
    block_manager: BlockManager,
    transaction_executor: TEP,
    view_factory: StateViewFactory,
    permission_verifier: PV,
}

impl<TEP: ExecutionPlatform + 'static, PV: PermissionVerifier + 'static> BlockValidator<TEP, PV>
where
    TEP: Clone,
    PV: Clone,
{
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        block_manager: BlockManager,
        transaction_executor: TEP,
        block_status_store: BlockValidationResultStore,
        permission_verifier: PV,
        view_factory: StateViewFactory,
    ) -> Self {
        let mut channels = vec![];
        for _ in 1..BLOCK_VALIDATOR_THREAD_NUM {
            let (tx, rx) = channel();
            channels.push((tx, Some(rx)));
        }
        BlockValidator {
            channels,
            index: Arc::new(AtomicUsize::new(0)),
            transaction_executor,
            validation_thread_exit: Arc::new(AtomicBool::new(false)),
            block_scheduler: BlockScheduler::new(block_manager.clone(), block_status_store.clone()),
            block_status_store,
            block_manager,
            view_factory,
            permission_verifier,
        }
    }

    pub fn stop(&self) {
        self.validation_thread_exit.store(true, Ordering::Relaxed);
    }

    fn setup_thread(
        &self,
        rcv: Receiver<(Block, Sender<BlockValidationResult>)>,
        error_return_sender: Sender<(Block, Sender<BlockValidationResult>)>,
    ) {
        let backgroundthread = thread::Builder::new();

        let validation1: Box<BlockValidation<ReturnValue = ()>> = Box::new(
            DuplicatesAndDependenciesValidation::new(self.block_manager.clone()),
        );

        let validation2: Box<BlockValidation<ReturnValue = ()>> =
            Box::new(OnChainRulesValidation::new(self.view_factory.clone()));

        let validation3: Box<BlockValidation<ReturnValue = ()>> =
            Box::new(PermissionValidation::new(self.permission_verifier.clone()));

        let validations = vec![validation1, validation2, validation3];

        let state_validation = BatchesInBlockValidation::new(self.transaction_executor.clone());

        let block_validations = BlockValidationProcessor::new(
            self.block_manager.clone(),
            validations,
            state_validation,
        );

        let exit = self.validation_thread_exit.clone();
        backgroundthread
            .spawn(move || loop {
                let (block, results_sender) = match rcv
                    .recv_timeout(Duration::from_millis(BLOCKVALIDATION_QUEUE_RECV_TIMEOUT))
                {
                    Err(RecvTimeoutError::Timeout) => {
                        if exit.load(Ordering::Relaxed) {
                            break;
                        }
                        continue;
                    }
                    Err(err) => {
                        error!("BlockValidation queue shut down unexpectedly: {}", err);
                        break;
                    }
                    Ok(b) => b,
                };

                if exit.load(Ordering::Relaxed) {
                    break;
                }
                let block_id = block.header_signature.clone();

                match block_validations.validate_block(&block) {
                    Ok(result) => {
                        info!("Block {} passed validation", block_id);
                        if let Err(err) = results_sender.send(result) {
                            warn!("During handling valid block: {:?}", err);
                            exit.store(true, Ordering::Relaxed);
                        }
                    }
                    Err(ValidationError::BlockValidationFailure(ref reason)) => {
                        warn!("Block {} failed validation: {}", &block_id, reason);
                        if let Err(err) = results_sender.send(BlockValidationResult {
                            block_id,
                            execution_results: vec![],
                            num_transactions: 0,
                            status: BlockStatus::Invalid,
                        }) {
                            warn!("During handling block failure: {:?}", err);
                            exit.store(true, Ordering::Relaxed);
                        }
                    }
                    Err(err) => {
                        warn!("Error during block validation: {:?}", err);
                        if let Err(err) = error_return_sender.send((block, results_sender)) {
                            warn!("During handling retry after an error: {:?}", err);
                            exit.store(true, Ordering::Relaxed);
                        }
                    }
                }
            })
            .expect("The background thread had an error");
    }

    pub fn start(&mut self) {
        let mut channels = vec![];
        {
            for (tx, rx) in &mut self.channels {
                let receiver = rx
                    .take()
                    .expect("For a single call of start, there will always be receivers to take");
                channels.push((receiver, tx.clone()));
            }
        }
        for (rx, tx) in channels {
            self.setup_thread(rx, tx);
        }
    }

    pub fn has_block(&self, block_id: &str) -> bool {
        self.block_scheduler.contains(block_id)
    }

    fn return_sender(&self) -> InternalSender {
        let index = self.index.load(Ordering::Relaxed);
        let (ref tx, _) = self.channels[index];

        if index >= self.channels.len() - 1 {
            self.index.store(0, Ordering::Relaxed);
        } else {
            self.index.store(index + 1, Ordering::Relaxed);
        }
        tx.clone()
    }

    pub fn submit_blocks_for_verification(
        &self,
        blocks: &[Block],
        response_sender: &Sender<BlockValidationResult>,
    ) {
        for block in self.block_scheduler.schedule(blocks.to_vec()) {
            let tx = self.return_sender();
            if let Err(err) = tx.send((block, response_sender.clone())) {
                warn!("During submit blocks for validation: {:?}", err);
                self.validation_thread_exit.store(true, Ordering::Relaxed);
            }
        }
    }

    pub fn process_pending(&self, block: &Block, response_sender: &Sender<BlockValidationResult>) {
        for block in self.block_scheduler.done(&block.header_signature) {
            let tx = self.return_sender();
            if let Err(err) = tx.send((block, response_sender.clone())) {
                warn!("During process pending: {:?}", err);
                self.validation_thread_exit.store(true, Ordering::Relaxed);
            }
        }
    }

    pub fn validate_block(&self, block: &Block) -> Result<(), ValidationError> {
        let validation1: Box<BlockValidation<ReturnValue = ()>> = Box::new(
            DuplicatesAndDependenciesValidation::new(self.block_manager.clone()),
        );

        let validation2: Box<BlockValidation<ReturnValue = ()>> =
            Box::new(OnChainRulesValidation::new(self.view_factory.clone()));

        let validation3: Box<BlockValidation<ReturnValue = ()>> =
            Box::new(PermissionValidation::new(self.permission_verifier.clone()));

        let validations = vec![validation1, validation2, validation3];

        let state_validation = BatchesInBlockValidation::new(self.transaction_executor.clone());

        let block_validations = BlockValidationProcessor::new(
            self.block_manager.clone(),
            validations,
            state_validation,
        );

        let result = block_validations.validate_block(block)?;
        self.block_status_store.insert(result);

        Ok(())
    }
}

impl<TEP: ExecutionPlatform + Clone, PV: PermissionVerifier + Clone> Clone
    for BlockValidator<TEP, PV>
{
    fn clone(&self) -> Self {
        let transaction_executor = self.transaction_executor.clone();
        let validation_thread_exit = Arc::clone(&self.validation_thread_exit);
        let index = Arc::clone(&self.index);

        BlockValidator {
            channels: self
                .channels
                .iter()
                .map(|s| {
                    let (tx, _) = s;
                    (tx.clone(), None)
                })
                .collect(),
            index,
            transaction_executor,
            validation_thread_exit,
            block_scheduler: self.block_scheduler.clone(),
            block_status_store: self.block_status_store.clone(),
            block_manager: self.block_manager.clone(),
            permission_verifier: self.permission_verifier.clone(),
            view_factory: self.view_factory.clone(),
        }
    }
}

trait StateBlockValidation {
    fn validate_block(
        &self,
        block: Block,
        previous_state_root: Option<&String>,
    ) -> Result<BlockValidationResult, ValidationError>;
}
/// A generic block validation. Returns a ValidationError::BlockValidationFailure on
/// validation failure. It is a dependent validation if it can return
/// ValidationError::BlockStoreUpdated and is an independent validation otherwise
trait BlockValidation: Send {
    type ReturnValue;

    fn validate_block(
        &self,
        block: &Block,
        previous_state_root: Option<&String>,
    ) -> Result<Self::ReturnValue, ValidationError>;
}

struct BlockValidationProcessor<SBV: BlockValidation<ReturnValue = BlockValidationResult>> {
    block_manager: BlockManager,
    validations: Vec<Box<BlockValidation<ReturnValue = ()>>>,
    state_validation: SBV,
}

impl<SBV: BlockValidation<ReturnValue = BlockValidationResult>> BlockValidationProcessor<SBV> {
    fn new(
        block_manager: BlockManager,
        validations: Vec<Box<BlockValidation<ReturnValue = ()>>>,
        state_validation: SBV,
    ) -> Self {
        BlockValidationProcessor {
            block_manager,
            validations,
            state_validation,
        }
    }

    fn validate_block(&self, block: &Block) -> Result<BlockValidationResult, ValidationError> {
        let previous_blocks_state_hash = self
            .block_manager
            .get(&[&block.previous_block_id])
            .next()
            .unwrap_or(None)
            .map(|b| b.state_root_hash.clone());

        for validation in &self.validations {
            match validation.validate_block(&block, previous_blocks_state_hash.as_ref()) {
                Ok(()) => (),
                Err(err) => return Err(err),
            }
        }

        self.state_validation
            .validate_block(&block, previous_blocks_state_hash.as_ref())
    }
}

/// Validate that all the batches are valid and all the transactions produce
/// the expected state hash.
struct BatchesInBlockValidation<TEP: ExecutionPlatform> {
    transaction_executor: TEP,
}

impl<TEP: ExecutionPlatform> BatchesInBlockValidation<TEP> {
    fn new(transaction_executor: TEP) -> Self {
        BatchesInBlockValidation {
            transaction_executor,
        }
    }
}

impl<TEP: ExecutionPlatform> BlockValidation for BatchesInBlockValidation<TEP> {
    type ReturnValue = BlockValidationResult;

    fn validate_block(
        &self,
        block: &Block,
        previous_state_root: Option<&String>,
    ) -> Result<BlockValidationResult, ValidationError> {
        let ending_state_hash = &block.state_root_hash;
        let null_state_hash = NULL_STATE_HASH.into();
        let state_root = previous_state_root.unwrap_or(&null_state_hash);
        let mut scheduler = self
            .transaction_executor
            .create_scheduler(state_root)
            .map_err(|err| {
                ValidationError::BlockValidationError(format!(
                    "Error during validation of block {} batches: {:?}",
                    &block.header_signature, err,
                ))
            })?;

        let greatest_batch_index = block.batches.len() - 1;
        let mut index = 0;
        for batch in &block.batches {
            if index < greatest_batch_index {
                scheduler
                    .add_batch(batch.clone(), None, false)
                    .map_err(|err| {
                        ValidationError::BlockValidationError(format!(
                            "While adding a batch to the schedule: {:?}",
                            err
                        ))
                    })?;
            } else {
                scheduler
                    .add_batch(batch.clone(), Some(ending_state_hash), false)
                    .map_err(|err| {
                        ValidationError::BlockValidationError(format!(
                            "While adding the last batch to the schedule: {:?}",
                            err
                        ))
                    })?;
            }
            index += 1;
        }
        scheduler.finalize(false).map_err(|err| {
            ValidationError::BlockValidationError(format!(
                "During call to scheduler.finalize: {:?}",
                err
            ))
        })?;
        let execution_results = scheduler
            .complete(true)
            .map_err(|err| {
                ValidationError::BlockValidationError(format!(
                    "During call to scheduler.complete: {:?}",
                    err
                ))
            })?
            .ok_or_else(|| {
                ValidationError::BlockValidationFailure(format!(
                    "Block {} failed validation: no execution results produced",
                    &block.header_signature
                ))
            })?;

        if let Some(ref actual_ending_state_hash) = execution_results.ending_state_hash {
            if ending_state_hash != actual_ending_state_hash {
                return Err(ValidationError::BlockValidationFailure(format!(
                "Block {} failed validation: expected state hash {}, validation found state hash {}",
                &block.header_signature,
                ending_state_hash,
                actual_ending_state_hash
            )));
            }
        } else {
            return Err(ValidationError::BlockValidationFailure(format!(
                "Block {} failed validation: no ending state hash was produced",
                &block.header_signature
            )));
        }

        let mut results = vec![];
        for (batch_id, transaction_execution_results) in execution_results.batch_results {
            if let Some(txn_results) = transaction_execution_results {
                for r in txn_results {
                    if !r.is_valid {
                        return Err(ValidationError::BlockValidationFailure(format!(
                            "Block {} failed validation: batch {} was invalid due to transaction {}",
                            &block.header_signature,
                            &batch_id,
                            &r.signature)));
                    }
                    results.push(r);
                }
            } else {
                return Err(ValidationError::BlockValidationFailure(format!(
                    "Block {} failed validation: batch {} did not have transaction results",
                    &block.header_signature, &batch_id
                )));
            }
        }
        Ok(BlockValidationResult {
            block_id: block.header_signature.clone(),
            num_transactions: results.len() as u64,
            execution_results: results,
            status: BlockStatus::Valid,
        })
    }
}

struct DuplicatesAndDependenciesValidation {
    block_manager: BlockManager,
}

impl DuplicatesAndDependenciesValidation {
    fn new(block_manager: BlockManager) -> Self {
        DuplicatesAndDependenciesValidation { block_manager }
    }
}

impl BlockValidation for DuplicatesAndDependenciesValidation {
    type ReturnValue = ();

    fn validate_block(&self, block: &Block, _: Option<&String>) -> Result<(), ValidationError> {
        let batch_ids: Vec<&String> = block.batches.iter().map(|b| &b.header_signature).collect();

        validate_no_duplicate_batches(
            &self.block_manager,
            &block.previous_block_id,
            batch_ids.as_slice(),
        )?;

        let txn_ids = block.batches.iter().fold(vec![], |mut arr, b| {
            for txn in &b.transactions {
                arr.push(&txn.header_signature);
            }
            arr
        });

        validate_no_duplicate_transactions(
            &self.block_manager,
            &block.previous_block_id,
            txn_ids.as_slice(),
        )?;

        let transactions = block.batches.iter().fold(vec![], |mut arr, b| {
            for txn in &b.transactions {
                arr.push(txn.clone());
            }
            arr
        });
        validate_transaction_dependencies(
            &self.block_manager,
            &block.previous_block_id,
            &transactions,
        )?;
        Ok(())
    }
}

struct PermissionValidation<PV: PermissionVerifier> {
    permission_verifier: PV,
}

impl<PV: PermissionVerifier> PermissionValidation<PV> {
    fn new(permission_verifier: PV) -> Self {
        PermissionValidation {
            permission_verifier,
        }
    }
}

impl<PV: PermissionVerifier> BlockValidation for PermissionValidation<PV> {
    type ReturnValue = ();

    fn validate_block(
        &self,
        block: &Block,
        prev_state_root: Option<&String>,
    ) -> Result<(), ValidationError> {
        if block.block_num != 0 {
            let state_root = prev_state_root.ok_or_else(|| {
                ValidationError::BlockValidationError(
                        format!("During permission check of block {} block_num is {} but missing a previous state root",
                            &block.header_signature, block.block_num))
            })?;
            for batch in &block.batches {
                let batch_id = &batch.header_signature;
                if !self
                    .permission_verifier
                    .is_batch_signer_authorized(batch, state_root)
                {
                    return Err(ValidationError::BlockValidationError(
                            format!("Block {} failed permission verification: batch {} signer is not authorized",
                            &block.header_signature,
                            batch_id)));
                }
            }
        }
        Ok(())
    }
}

struct OnChainRulesValidation {
    view_factory: StateViewFactory,
}

impl OnChainRulesValidation {
    fn new(view_factory: StateViewFactory) -> Self {
        OnChainRulesValidation { view_factory }
    }
}

impl BlockValidation for OnChainRulesValidation {
    type ReturnValue = ();

    fn validate_block(
        &self,
        block: &Block,
        prev_state_root: Option<&String>,
    ) -> Result<(), ValidationError> {
        if block.block_num != 0 {
            let state_root = prev_state_root.ok_or_else(|| {
                ValidationError::BlockValidationError(
                        format!("During check of on-chain rules for block {}, block num was {}, but missing a previous state root",
                            &block.header_signature,
                            block.block_num))
            })?;
            let settings_view: SettingsView =
                self.view_factory.create_view(state_root).map_err(|err| {
                    ValidationError::BlockValidationError(format!(
                        "During validate_on_chain_rules, error creating settings view: {:?}",
                        err
                    ))
                })?;
            let batches: Vec<&Batch> = block.batches.iter().collect();
            if !enforce_validation_rules(&settings_view, &block.signer_public_key, &batches) {
                return Err(ValidationError::BlockValidationFailure(format!(
                    "Block {} failed validation rules",
                    &block.header_signature
                )));
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod test {

    use super::*;
    use journal::{
        block_store::{BlockStore, BlockStoreError},
        NULL_BLOCK_IDENTIFIER,
    };
    use std::sync::Mutex;

    #[test]
    fn test_validation_processor_genesis() {
        let block_manager = BlockManager::new();
        let block_a = create_block("A", NULL_BLOCK_IDENTIFIER, vec![]);

        let validation1: Box<BlockValidation<ReturnValue = ()>> = Box::new(Mock1::new(Ok(())));

        let validation2: Box<BlockValidation<ReturnValue = ()>> =
            Box::new(Mock2::new(Ok(()), Ok(())));
        let validations = vec![validation1, validation2];
        let state_block_validation = Mock1::new(Ok(BlockValidationResult::new(
            "".into(),
            vec![],
            0,
            BlockStatus::Valid,
        )));

        let validation_processor =
            BlockValidationProcessor::new(block_manager, validations, state_block_validation);
        assert!(validation_processor.validate_block(&block_a).is_ok());
    }

    /*
     * Test mocks that are stand-ins for the individual validation handlers
     */

    struct Mock1<R>
    where
        R: Clone,
    {
        result: R,
    }

    impl<R: Clone> Mock1<R> {
        fn new(result: R) -> Self {
            Mock1 { result }
        }
    }

    impl BlockValidation for Mock1<Result<BlockValidationResult, ValidationError>> {
        type ReturnValue = BlockValidationResult;

        fn validate_block(
            &self,
            _block: &Block,
            _previous_state_root: Option<&String>,
        ) -> Result<BlockValidationResult, ValidationError> {
            self.result.clone()
        }
    }

    impl BlockValidation for Mock1<Result<(), ValidationError>> {
        type ReturnValue = ();

        fn validate_block(
            &self,
            _block: &Block,
            _previous_state_root: Option<&String>,
        ) -> Result<(), ValidationError> {
            self.result.clone()
        }
    }

    struct Mock2<R>
    where
        R: Clone,
    {
        first: R,
        every_other: R,
        called: Mutex<bool>,
    }

    impl<R: Clone> Mock2<R> {
        fn new(first: R, every_other: R) -> Self {
            Mock2 {
                first,
                every_other,
                called: Mutex::new(false),
            }
        }
    }

    impl BlockValidation for Mock2<Result<(), ValidationError>> {
        type ReturnValue = ();

        fn validate_block(
            &self,
            _block: &Block,
            _previous_state_root: Option<&String>,
        ) -> Result<(), ValidationError> {
            if *self.called.lock().expect("Error acquiring Mock2 lock") {
                return self.every_other.clone();
            }
            {
                let mut called = self.called.lock().expect("Error acquiring Mock2 lock");
                *called = true;
            }
            self.first.clone()
        }
    }

    impl BlockStore for Mock1<Option<Block>> {
        fn iter(&self) -> Result<Box<Iterator<Item = Block>>, BlockStoreError> {
            Ok(Box::new(self.result.clone().into_iter()))
        }

        fn get<'a>(
            &'a self,
            _block_ids: &[&str],
        ) -> Result<Box<Iterator<Item = Block> + 'a>, BlockStoreError> {
            unimplemented!();
        }

        fn put(&mut self, _block: Vec<Block>) -> Result<(), BlockStoreError> {
            unimplemented!();
        }

        fn delete(&mut self, _block_ids: &[&str]) -> Result<Vec<Block>, BlockStoreError> {
            unimplemented!();
        }
    }

    fn create_block(block_id: &str, previous_id: &str, batches: Vec<Batch>) -> Block {
        let batch_ids = batches.iter().map(|b| b.header_signature.clone()).collect();
        Block {
            header_signature: block_id.into(),
            batches,
            state_root_hash: "".into(),
            consensus: vec![],
            batch_ids,
            signer_public_key: "".into(),
            previous_block_id: previous_id.into(),
            block_num: 0,
            header_bytes: vec![],
        }
    }
}
