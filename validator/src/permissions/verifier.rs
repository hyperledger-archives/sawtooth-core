/*
 * Copyright 2018 Bitwise IO
 * Copyright 2019 Cargill Incorporated
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
use transaction::Transaction;

use super::error::IdentityError;
use super::{IdentitySource, Permission, Policy, Role};

// Roles
const ROLE_TRANSACTOR: &str = "transactor";
const ROLE_BATCH_TRANSACTOR: &str = "transactor.batch_signer";
const ROLE_TXN_TRANSACTOR: &str = "transactor.transaction_signer";

const POLICY_DEFAULT: &str = "default";

const ANY_KEY: &str = "*";

pub struct PermissionVerifier {
    identities: Box<dyn IdentitySource>,
}

impl PermissionVerifier {
    pub fn new(identities: Box<dyn IdentitySource>) -> Self {
        PermissionVerifier { identities }
    }
    /// Check the batch signing key against the allowed transactor
    /// permissions. The roles being checked are the following, from first
    /// to last:
    ///     "transactor.batch_signer"
    ///     "transactor"
    ///     "default"
    ///
    /// The first role that is set will be the one used to enforce if the
    /// batch signer is allowed.
    pub fn is_batch_signer_authorized(&self, batch: &Batch) -> Result<bool, IdentityError> {
        Self::is_batch_allowed(&*self.identities, batch, Some(POLICY_DEFAULT))
    }

    fn is_batch_allowed(
        identity_source: &dyn IdentitySource,
        batch: &Batch,
        default_policy: Option<&str>,
    ) -> Result<bool, IdentityError> {
        let policy_name: Option<String> = identity_source
            .get_role(ROLE_BATCH_TRANSACTOR)
            .and_then(|found| {
                if found.is_some() {
                    Ok(found)
                } else {
                    identity_source.get_role(ROLE_TRANSACTOR)
                }
            })?
            .map(|role| role.policy_name)
            .or(default_policy.map(ToString::to_string));

        let policy = if let Some(name) = policy_name {
            identity_source.get_policy(&name)?
        } else {
            None
        };

        let allowed = policy
            .map(|policy| Self::is_allowed(&batch.signer_public_key, &policy))
            .unwrap_or(true);

        if !allowed {
            debug!(
                "Batch Signer: {} is not permitted.",
                &batch.signer_public_key
            );
            return Ok(false);
        }

        Self::is_transaction_allowed(identity_source, &batch.transactions, default_policy)
    }

    /// Check the transaction signing key against the allowed transactor
    /// permissions. The roles being checked are the following, from first
    /// to last:
    ///     "transactor.transaction_signer.<TP_Name>"
    ///     "transactor.transaction_signer"
    ///     "transactor"
    ///
    /// If a default is supplied, that is used.
    ///
    /// The first role that is set will be the one used to enforce if the
    /// transaction signer is allowed.
    fn is_transaction_allowed(
        identity_source: &dyn IdentitySource,
        transactions: &[Transaction],
        default_policy: Option<&str>,
    ) -> Result<bool, IdentityError> {
        let general_txn_policy_name: Option<String> = identity_source
            .get_role(ROLE_TXN_TRANSACTOR)
            .and_then(|found| {
                if found.is_some() {
                    Ok(found)
                } else {
                    identity_source.get_role(ROLE_TRANSACTOR)
                }
            })?
            .map(|role| role.policy_name)
            .or(default_policy.map(ToString::to_string));

        for transaction in transactions {
            let policy_name: Option<String> = identity_source
                .get_role(&format!(
                    "{}.{}",
                    ROLE_TXN_TRANSACTOR, transaction.family_name
                ))?
                .map(|role| role.policy_name);

            let policy =
                if let Some(name) = policy_name.as_ref().or(general_txn_policy_name.as_ref()) {
                    identity_source.get_policy(name)?
                } else {
                    None
                };

            if let Some(policy) = policy {
                if !Self::is_allowed(&transaction.signer_public_key, &policy) {
                    debug!(
                        "Transaction Signer: {} is not permitted.",
                        &transaction.signer_public_key
                    );
                    return Ok(false);
                }
            }
        }
        Ok(true)
    }

    fn is_allowed(public_key: &str, policy: &Policy) -> bool {
        for permission in policy.permissions() {
            match permission {
                Permission::PermitKey(key) => {
                    if key == public_key || key == ANY_KEY {
                        return true;
                    }
                }
                Permission::DenyKey(key) => {
                    if key == public_key || key == ANY_KEY {
                        return false;
                    }
                }
            }
        }

        false
    }
}

struct EmptyIdentitySource {}

impl IdentitySource for EmptyIdentitySource {
    fn get_role(&self, _name: &str) -> Result<Option<Role>, IdentityError> {
        Ok(None)
    }

    fn get_policy(&self, _name: &str) -> Result<Option<Policy>, IdentityError> {
        Ok(None)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;

    use permissions::error::IdentityError;
    use permissions::{IdentitySource, Permission, Policy, Role};

    #[test]
    /// Test that if no roles are set and no default policy is set,
    /// permit all is used.
    fn allow_all_with_no_permissions() {
        let batch = create_batches(1, 1, "test_pubkey")
            .into_iter()
            .next()
            .unwrap();

        let permission_verifier = PermissionVerifier::new(Box::from(TestIdentitySource::default()));

        assert!(permission_verifier
            .is_batch_signer_authorized(&batch)
            .unwrap());
    }

    #[test]
    /// Test that if no roles are set, the default policy is used.
    ///     1. Set default policy to permit all. Batch should be allowed.
    ///     2. Set default policy to deny all. Batch should be rejected.
    fn default_policy_permission() {
        let batch = create_batches(1, 1, "test_pubkey")
            .into_iter()
            .next()
            .unwrap();

        {
            let mut on_chain_identities = TestIdentitySource::default();
            on_chain_identities.add_policy(Policy::new(
                "default",
                vec![Permission::PermitKey("*".into())],
            ));
            let permission_verifier = on_chain_verifier(on_chain_identities);
            assert!(permission_verifier
                .is_batch_signer_authorized(&batch)
                .unwrap());
        }

        {
            let mut on_chain_identities = TestIdentitySource::default();
            on_chain_identities.add_policy(Policy::new(
                "default",
                vec![Permission::DenyKey("*".into())],
            ));
            let permission_verifier = on_chain_verifier(on_chain_identities);
            assert!(!permission_verifier
                .is_batch_signer_authorized(&batch)
                .unwrap());
        }
    }

    #[test]
    /// Test that role: "transactor" is checked properly.
    ///     1. Set policy to permit signing key. Batch should be allowed.
    ///     2. Set policy to permit some other key. Batch should be rejected.
    fn transactor_role() {
        let pub_key = "test_pubkey".to_string();
        let batch = create_batches(1, 1, &pub_key).into_iter().next().unwrap();

        {
            let mut on_chain_identities = TestIdentitySource::default();
            on_chain_identities.add_policy(Policy::new(
                "policy1",
                vec![Permission::PermitKey(pub_key.clone())],
            ));
            on_chain_identities.add_role(Role::new("transactor", "policy1"));

            let permission_verifier = on_chain_verifier(on_chain_identities);
            assert!(permission_verifier
                .is_batch_signer_authorized(&batch)
                .unwrap());
        }
        {
            let mut on_chain_identities = TestIdentitySource::default();
            on_chain_identities
                .add_policy(Policy::new("policy1", vec![Permission::DenyKey(pub_key)]));
            on_chain_identities.add_role(Role::new("transactor", "policy1"));

            let permission_verifier = on_chain_verifier(on_chain_identities);
            assert!(!permission_verifier
                .is_batch_signer_authorized(&batch)
                .unwrap());
        }
    }

    #[test]
    /// Test that role: "transactor.batch_signer" is checked properly.
    ///     1. Set policy to permit signing key. Batch should be allowed.
    ///     2. Set policy to permit some other key. Batch should be rejected.
    fn transactor_batch_signer_role() {
        let pub_key = "test_pubkey".to_string();
        let batch = create_batches(1, 1, &pub_key).into_iter().next().unwrap();

        {
            let mut on_chain_identities = TestIdentitySource::default();
            on_chain_identities.add_policy(Policy::new(
                "policy1",
                vec![Permission::PermitKey(pub_key.clone())],
            ));
            on_chain_identities.add_role(Role::new("transactor.batch_signer", "policy1"));

            let permission_verifier = on_chain_verifier(on_chain_identities);
            assert!(permission_verifier
                .is_batch_signer_authorized(&batch)
                .unwrap());
        }
        {
            let mut on_chain_identities = TestIdentitySource::default();
            on_chain_identities
                .add_policy(Policy::new("policy1", vec![Permission::DenyKey(pub_key)]));
            on_chain_identities.add_role(Role::new("transactor.batch_signer", "policy1"));

            let permission_verifier = on_chain_verifier(on_chain_identities);
            assert!(!permission_verifier
                .is_batch_signer_authorized(&batch)
                .unwrap());
        }
    }

    #[test]
    /// Test that role: "transactor.transaction_signer" is checked properly.
    ///     1. Set policy to permit signing key. Batch should be allowed.
    ///     2. Set policy to permit some other key. Batch should be rejected.
    fn transactor_transaction_signer_role() {
        let pub_key = "test_pubkey".to_string();
        let batch = create_batches(1, 1, &pub_key).into_iter().next().unwrap();

        {
            let mut on_chain_identities = TestIdentitySource::default();
            on_chain_identities
                .add_policy(Policy::new("policy1", vec![Permission::PermitKey(pub_key)]));
            on_chain_identities.add_role(Role::new("transactor.transaction_signer", "policy1"));

            let permission_verifier = on_chain_verifier(on_chain_identities);
            assert!(permission_verifier
                .is_batch_signer_authorized(&batch)
                .unwrap());
        }
        {
            let mut on_chain_identities = TestIdentitySource::default();
            on_chain_identities.add_policy(Policy::new(
                "policy1",
                vec![Permission::PermitKey("other".to_string())],
            ));
            on_chain_identities.add_role(Role::new("transactor.transaction_signer", "policy1"));

            let permission_verifier = on_chain_verifier(on_chain_identities);
            assert!(!permission_verifier
                .is_batch_signer_authorized(&batch)
                .unwrap());
        }
    }

    #[test]
    /// Test that role: "transactor.transaction_signer.intkey" is checked properly.
    ///     1. Set policy to permit signing key. Batch should be allowed.
    ///     2. Set policy to permit some other key. Batch should be rejected.
    fn transactor_transaction_signer_transaction_family() {
        let pub_key = "test_pubkey".to_string();
        let batch = create_batches(1, 1, &pub_key).into_iter().next().unwrap();

        {
            let mut on_chain_identities = TestIdentitySource::default();
            on_chain_identities
                .add_policy(Policy::new("policy1", vec![Permission::PermitKey(pub_key)]));
            on_chain_identities
                .add_role(Role::new("transactor.transaction_signer.intkey", "policy1"));

            let permission_verifier = on_chain_verifier(on_chain_identities);
            assert!(permission_verifier
                .is_batch_signer_authorized(&batch)
                .unwrap());
        }
        {
            let mut on_chain_identities = TestIdentitySource::default();
            on_chain_identities.add_policy(Policy::new(
                "policy1",
                vec![Permission::PermitKey("other".to_string())],
            ));
            on_chain_identities
                .add_role(Role::new("transactor.transaction_signer.intkey", "policy1"));

            let permission_verifier = on_chain_verifier(on_chain_identities);
            assert!(!permission_verifier
                .is_batch_signer_authorized(&batch)
                .unwrap());
        }
    }

    fn on_chain_verifier(identity_source: TestIdentitySource) -> PermissionVerifier {
        PermissionVerifier::new(Box::new(identity_source))
    }

    fn create_transactions(count: usize, pub_key: &str) -> Vec<Transaction> {
        (0..count)
            .map(|i| Transaction {
                batcher_public_key: pub_key.to_string(),
                signer_public_key: pub_key.to_string(),
                header_signature: format!("signature-{i}"),
                payload: vec![],
                dependencies: vec![],
                family_name: "intkey".into(),
                family_version: "1.0".into(),
                inputs: vec![],
                outputs: vec![],
                payload_sha512: format!("nonesense-{i}"),
                header_bytes: vec![],
                nonce: format!("{i}"),
            })
            .collect()
    }

    fn create_batches(count: usize, txns_per_batch: usize, pub_key: &str) -> Vec<Batch> {
        (0..count)
            .map(|i| {
                let txns = create_transactions(txns_per_batch, pub_key);
                let txn_ids = txns
                    .iter()
                    .map(|txn| txn.header_signature.clone())
                    .collect();
                Batch {
                    signer_public_key: pub_key.to_string(),
                    transactions: txns,
                    transaction_ids: txn_ids,
                    header_signature: format!("batch-signature-{i}"),
                    header_bytes: vec![],
                    trace: false,
                }
            })
            .collect()
    }

    #[derive(Default)]
    struct TestIdentitySource {
        policies: HashMap<String, Policy>,
        roles: HashMap<String, Role>,
    }

    impl TestIdentitySource {
        fn add_policy(&mut self, policy: Policy) {
            self.policies.insert(policy.name.clone(), policy);
        }

        fn add_role(&mut self, role: Role) {
            self.roles.insert(role.name.clone(), role);
        }
    }

    impl IdentitySource for TestIdentitySource {
        fn get_role(&self, name: &str) -> Result<Option<Role>, IdentityError> {
            Ok(self.roles.get(name).cloned())
        }

        fn get_policy(&self, name: &str) -> Result<Option<Policy>, IdentityError> {
            Ok(self.policies.get(name).cloned())
        }
    }
}
