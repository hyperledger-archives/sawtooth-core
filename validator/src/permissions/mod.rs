/*
 * Copyright 2018 Bitwise IO
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
pub mod error;
mod state_source;
pub mod verifier;

pub use self::error::IdentityError;

#[derive(Clone)]
pub enum Permission {
    PermitKey(String),
    DenyKey(String),
}

#[allow(dead_code)]
#[derive(Clone)]
pub struct Policy {
    name: String,
    permissions: Vec<Permission>,
}

impl Policy {
    pub fn new<S: Into<String>>(name: S, permissions: Vec<Permission>) -> Self {
        Policy {
            name: name.into(),
            permissions,
        }
    }

    pub fn permissions(&self) -> &[Permission] {
        &self.permissions
    }
}

#[allow(dead_code)]
#[derive(Clone)]
pub struct Role {
    name: String,
    policy_name: String,
}

impl Role {
    pub fn new<N: Into<String>, P: Into<String>>(name: N, policy_name: P) -> Self {
        Role {
            name: name.into(),
            policy_name: policy_name.into(),
        }
    }
}

pub trait IdentitySource: Sync + Send {
    fn get_role(&self, name: &str) -> Result<Option<Role>, IdentityError>;
    fn get_policy(&self, name: &str) -> Result<Option<Policy>, IdentityError>;
}