/*
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

use crate::proto::identity::Policy_EntryType;
use crate::state::identity_view::IdentityView;

use super::{IdentityError, IdentitySource, Permission, Policy, Role};

impl IdentitySource for IdentityView {
    fn get_role(&self, name: &str) -> Result<Option<Role>, IdentityError> {
        let role = IdentityView::get_role(self, name).map_err(|err| {
            IdentityError::ReadError(format!("unable to read role from state: {err:?}"))
        })?;

        Ok(role.map(|mut role| Role::new(role.take_name(), role.take_policy_name())))
    }

    fn get_policy(&self, name: &str) -> Result<Option<Policy>, IdentityError> {
        let policy = IdentityView::get_policy(self, name).map_err(|err| {
            IdentityError::ReadError(format!("unable to read policy from state: {err:?}"))
        })?;

        if let Some(mut policy) = policy {
            let permissions: Result<Vec<Permission>, IdentityError> = policy
                .take_entries()
                .into_iter()
                .map(|mut entry| match entry.get_field_type() {
                    Policy_EntryType::PERMIT_KEY => Ok(Permission::PermitKey(entry.take_key())),
                    Policy_EntryType::DENY_KEY => Ok(Permission::DenyKey(entry.take_key())),
                    Policy_EntryType::ENTRY_TYPE_UNSET => Err(IdentityError::ReadError(format!(
                        "policy {} is contains invalid type",
                        entry.get_key()
                    ))),
                })
                .collect();

            Ok(Some(Policy::new(policy.take_name(), permissions?)))
        } else {
            Ok(None)
        }
    }
}
