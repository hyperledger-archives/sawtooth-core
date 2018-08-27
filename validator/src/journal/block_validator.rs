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

use block::Block;
use execution::execution_platform::{ExecutionPlatform, NULL_STATE_HASH};
use gossip::permission_verifier::PermissionVerifier;
use journal::block_store::{BatchIndex, TransactionIndex};
use journal::chain_commit_state::{ChainCommitState, ChainCommitStateError};
use journal::{block_manager::BlockManager, block_store::BlockStore, block_wrapper::BlockStatus};
use scheduler::TxnExecutionResult;
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
