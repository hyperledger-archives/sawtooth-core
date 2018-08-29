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

use cpython;
use cpython::{FromPyObject, ObjectProtocol, PyObject, Python};

use batch::Batch;
use block::Block;
use execution::execution_platform::{ExecutionPlatform, NULL_STATE_HASH};
use gossip::permission_verifier::PermissionVerifier;
use journal::block_store::{BatchIndex, TransactionIndex};
use journal::chain_commit_state::{ChainCommitState, ChainCommitStateError};
use journal::validation_rule_enforcer::enforce_validation_rules;
use journal::{block_manager::BlockManager, block_store::BlockStore, block_wrapper::BlockStatus};
use scheduler::TxnExecutionResult;
use state::{settings_view::SettingsView, state_view_factory::StateViewFactory};
use std::sync::mpsc::Sender;

#[derive(Clone, Debug, PartialEq)]
pub enum ValidationError {
    BlockValidationFailure(String),
    BlockValidationError(String),
    BlockStoreUpdated,
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

pub trait BlockValidator: Sync + Send + Clone {
    fn has_block(&self, block_id: &str) -> bool;

    fn validate_block(&self, block: Block) -> Result<(), ValidationError>;

    fn submit_blocks_for_verification(
        &self,
        blocks: &[Block],
        response_sender: Sender<BlockValidationResult>,
    );

    fn process_pending(&self, block: &Block, response_sender: Sender<BlockValidationResult>);
}

pub trait BlockStatusStore {
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

impl<'source> FromPyObject<'source> for BlockValidationResult {
    fn extract(py: Python, obj: &'source PyObject) -> cpython::PyResult<Self> {
        let status: BlockStatus = obj.getattr(py, "status")?.extract(py)?;
        let execution_results: Vec<TxnExecutionResult> =
            obj.getattr(py, "execution_results")?.extract(py)?;
        let block_id: String = obj.getattr(py, "block_id")?.extract(py)?;
        let num_transactions = obj.getattr(py, "num_transactions")?.extract(py)?;

        Ok(BlockValidationResult {
            block_id,
            execution_results,
            num_transactions,
            status,
        })
    }
}

/// A generic block validation. Returns a ValidationError::BlockValidationFailure on
/// validation failure. It is a dependent validation if it can return
/// ValidationError::BlockStoreUpdated and is an independent validation otherwise
trait BlockValidation {
    type ReturnValue;

    fn validate_block(
        &self,
        block: &Block,
        previous_state_root: Option<&String>,
    ) -> Result<Self::ReturnValue, ValidationError>;
}

/// A check that determines if the Dependent checks are honored. If this check
/// returns false, the dependent checks are honored.
trait BlockStoreUpdatedCheck {
    fn check_chain_head_updated(
        &self,
        expected_chain_head_id: Option<&String>,
    ) -> Result<bool, ValidationError>;
}

struct BlockValidationProcessor<
    BS: BlockStore,
    SBV: BlockValidation<ReturnValue = BlockValidationResult>,
    C: BlockStoreUpdatedCheck,
> {
    block_store: BS,
    block_manager: BlockManager,
    dependent_validations: Vec<Box<BlockValidation<ReturnValue = ()>>>,
    independent_validations: Vec<Box<BlockValidation<ReturnValue = ()>>>,
    state_validation: SBV,
    check: C,
}

impl<
        BS: BlockStore,
        SBV: BlockValidation<ReturnValue = BlockValidationResult>,
        C: BlockStoreUpdatedCheck,
    > BlockValidationProcessor<BS, SBV, C>
{
    fn new(
        block_store: BS,
        block_manager: BlockManager,
        dependent_validations: Vec<Box<BlockValidation<ReturnValue = ()>>>,
        independent_validations: Vec<Box<BlockValidation<ReturnValue = ()>>>,
        state_validation: SBV,
        check: C,
    ) -> Self {
        BlockValidationProcessor {
            block_store,
            block_manager,
            dependent_validations,
            independent_validations,
            state_validation,
            check,
        }
    }

    fn validate_block(&self, block: &Block) -> Result<BlockValidationResult, ValidationError> {
        let previous_blocks_state_hash = self
            .block_manager
            .get(&[&block.previous_block_id])
            .next()
            .unwrap_or(None)
            .map(|b| b.state_root_hash.clone());

        let checks = 'outer: loop {
            let chain_head_option = self
                .block_store
                .iter()
                .map_err(|err| {
                    ValidationError::BlockValidationError(format!(
                        "There was an error reading from the BlockStore: {:?}",
                        err
                    ))
                })?
                .next()
                .map(|b| b.header_signature.clone());
            let mut dependent_checks = vec![];
            for validation in &self.dependent_validations {
                match validation.validate_block(&block, previous_blocks_state_hash.as_ref()) {
                    Ok(()) => (),
                    Err(ValidationError::BlockStoreUpdated) => {
                        warn!(
                            "Blockstore updated during validation of block {}, retrying checks",
                            &block.header_signature
                        );
                        continue 'outer;
                    }
                    Err(err) => dependent_checks.push(Err(err)),
                }
            }

            if !self
                .check
                .check_chain_head_updated(chain_head_option.as_ref())?
            {
                break dependent_checks;
            }
        };
        for check in checks {
            check?;
        }

        for validation in &self.independent_validations {
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
            .ok_or(ValidationError::BlockValidationFailure(format!(
                "Block {} failed validation: no execution results produced",
                &block.header_signature
            )))?;

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

struct DuplicatesAndDependenciesValidation<B: BatchIndex, T: TransactionIndex, BS: BlockStore> {
    batch_index: B,
    transaction_index: T,
    block_store: BS,
    block_manager: BlockManager,
}

impl<B: BatchIndex, T: TransactionIndex, BS: BlockStore>
    DuplicatesAndDependenciesValidation<B, T, BS>
{
    fn new(
        batch_index: B,
        transaction_index: T,
        block_store: BS,
        block_manager: BlockManager,
    ) -> Self {
        DuplicatesAndDependenciesValidation {
            batch_index,
            transaction_index,
            block_store,
            block_manager,
        }
    }
}

impl<B: BatchIndex, T: TransactionIndex, BS: BlockStore> BlockValidation
    for DuplicatesAndDependenciesValidation<B, T, BS>
{
    type ReturnValue = ();

    fn validate_block(&self, block: &Block, _: Option<&String>) -> Result<(), ValidationError> {
        let chain_commit_state = ChainCommitState::new(
            &block.previous_block_id,
            &self.block_manager,
            &self.batch_index,
            &self.transaction_index,
            &self.block_store,
        )?;

        let batch_ids = block
            .batches
            .iter()
            .map(|b| b.header_signature.clone())
            .collect();

        chain_commit_state.validate_no_duplicate_batches(batch_ids)?;

        let txn_ids = block.batches.iter().fold(vec![], |mut arr, b| {
            for txn in &b.transactions {
                arr.push(txn.header_signature.clone());
            }
            arr
        });

        chain_commit_state.validate_no_duplicate_transactions(txn_ids)?;

        let transactions = block.batches.iter().fold(vec![], |mut arr, b| {
            for txn in &b.transactions {
                arr.push(txn.clone());
            }
            arr
        });
        chain_commit_state.validate_transaction_dependencies(&transactions)?;
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
            let state_root = prev_state_root
                .ok_or(
                    ValidationError::BlockValidationError(
                        format!("During permission check of block {} block_num is {} but missing a previous state root",
                            &block.header_signature, block.block_num)))?;
            for batch in &block.batches {
                let batch_id = &batch.header_signature;
                if !self
                    .permission_verifier
                    .is_batch_signer_authorized(batch, state_root, true)
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
            let state_root = prev_state_root
                .ok_or(
                    ValidationError::BlockValidationError(
                        format!("During check of on-chain rules for block {}, block num was {}, but missing a previous state root",
                            &block.header_signature,
                            block.block_num)))?;
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

struct ChainHeadCheck<BS: BlockStore> {
    block_store: BS,
}

impl<BS: BlockStore> ChainHeadCheck<BS> {
    fn new(block_store: BS) -> Self {
        ChainHeadCheck { block_store }
    }
}

impl<BS: BlockStore> BlockStoreUpdatedCheck for ChainHeadCheck<BS> {
    fn check_chain_head_updated(
        &self,
        original_chain_head: Option<&String>,
    ) -> Result<bool, ValidationError> {
        let chain_head = self
            .block_store
            .iter()
            .map_err(|err| {
                ValidationError::BlockValidationError(format!(
                    "There was an error reading from the BlockStore: {:?}",
                    err
                ))
            })?
            .next()
            .map(|b| b.header_signature.clone());

        if chain_head.as_ref() != original_chain_head {
            return Ok(true);
        }
        Ok(false)
    }
}

#[cfg(test)]
mod test {

    use super::*;
    use journal::{block_store::BlockStoreError, NULL_BLOCK_IDENTIFIER};
    use std::sync::Mutex;

    #[test]
    fn test_validation_processor_genesis() {
        let block_manager = BlockManager::new();
        let block_a = create_block("A", NULL_BLOCK_IDENTIFIER, vec![]);

        let block_store = Mock1::new(None);

        let dependent_validation: Box<BlockValidation<ReturnValue = ()>> =
            Box::new(Mock2::new(Err(ValidationError::BlockStoreUpdated), Ok(())));

        let dependent_validations = vec![dependent_validation];

        let independent_validation: Box<BlockValidation<ReturnValue = ()>> =
            Box::new(Mock2::new(Ok(()), Ok(())));
        let independent_validations = vec![independent_validation];
        let state_block_validation = Mock1::new(Ok(BlockValidationResult::new(
            "".into(),
            vec![],
            0,
            BlockStatus::Valid,
        )));

        let check = Mock2::new(Ok(true), Ok(false));

        let validation_processor = BlockValidationProcessor::new(
            block_store,
            block_manager,
            dependent_validations,
            independent_validations,
            state_block_validation,
            check,
        );
        assert!(validation_processor.validate_block(&block_a).is_ok());
    }

    #[test]
    fn test_validation_processor_chain_head_updated() {
        let block_manager = BlockManager::new();
        let block_a = create_block("A", NULL_BLOCK_IDENTIFIER, vec![]);
        let block_b = create_block("B", "A", vec![]);

        block_manager
            .put(vec![block_a.clone()])
            .expect("Block manager errored on `put`");
        let block_store = Mock1::new(Some(block_a));

        let dependent_validation: Box<BlockValidation<ReturnValue = ()>> =
            Box::new(Mock2::new(Err(ValidationError::BlockStoreUpdated), Ok(())));

        let dependent_validations = vec![dependent_validation];

        let independent_validation: Box<BlockValidation<ReturnValue = ()>> =
            Box::new(Mock2::new(Ok(()), Ok(())));
        let independent_validations = vec![independent_validation];
        let state_block_validation = Mock1::new(Ok(BlockValidationResult::new(
            "".into(),
            vec![],
            0,
            BlockStatus::Valid,
        )));

        let check = Mock2::new(Ok(true), Ok(false));

        let validation_processor = BlockValidationProcessor::new(
            block_store,
            block_manager,
            dependent_validations,
            independent_validations,
            state_block_validation,
            check,
        );
        assert!(validation_processor.validate_block(&block_b).is_ok());
    }

    #[test]
    fn test_check_chain_head_updated_false() {
        let block_a = create_block("A", NULL_BLOCK_IDENTIFIER, vec![]);

        let original_chain_head = Some(block_a.header_signature.clone());

        let block_store = Mock1::new(Some(block_a.clone()));

        let check = ChainHeadCheck::new(block_store);

        assert_eq!(
            check.check_chain_head_updated(original_chain_head.as_ref()),
            Ok(false)
        );
    }

    #[test]
    fn test_check_chain_head_updated_true() {
        let block_a = create_block("A", NULL_BLOCK_IDENTIFIER, vec![]);
        let block_b = create_block("B", "A", vec![]);

        let original_chain_head = Some(block_a.header_signature.clone());

        let block_store = Mock1::new(Some(block_b));

        let check = ChainHeadCheck::new(block_store);

        assert_eq!(
            check.check_chain_head_updated(original_chain_head.as_ref()),
            Ok(true)
        );
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

    impl BlockStoreUpdatedCheck for Mock1<Result<bool, ValidationError>> {
        fn check_chain_head_updated(
            &self,
            expected_chain_head_id: Option<&String>,
        ) -> Result<bool, ValidationError> {
            self.result.clone()
        }
    }

    impl BlockValidation for Mock1<Result<BlockValidationResult, ValidationError>> {
        type ReturnValue = BlockValidationResult;

        fn validate_block(
            &self,
            block: &Block,
            previous_state_root: Option<&String>,
        ) -> Result<BlockValidationResult, ValidationError> {
            self.result.clone()
        }
    }

    impl BlockValidation for Mock1<Result<(), ValidationError>> {
        type ReturnValue = ();

        fn validate_block(
            &self,
            block: &Block,
            previous_state_root: Option<&String>,
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

    impl BlockStoreUpdatedCheck for Mock2<Result<bool, ValidationError>> {
        fn check_chain_head_updated(
            &self,
            expected_chain_head_id: Option<&String>,
        ) -> Result<bool, ValidationError> {
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

    impl BlockValidation for Mock2<Result<(), ValidationError>> {
        type ReturnValue = ();

        fn validate_block(
            &self,
            block: &Block,
            previous_state_root: Option<&String>,
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
            block_ids: &[&str],
        ) -> Result<Box<Iterator<Item = Block> + 'a>, BlockStoreError> {
            unimplemented!();
        }

        fn put(&mut self, block: Vec<Block>) -> Result<(), BlockStoreError> {
            unimplemented!();
        }

        fn delete(&mut self, block_ids: &[&str]) -> Result<Vec<Block>, BlockStoreError> {
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
