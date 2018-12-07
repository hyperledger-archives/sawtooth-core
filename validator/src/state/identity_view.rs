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

use std::iter::repeat;

use hashlib::sha256_digest_str;
use protobuf;

use proto::identity::Policy;
use proto::identity::PolicyList;
use proto::identity::Role;
use proto::identity::RoleList;

use state::StateDatabaseError;
use state::StateReader;

/// The namespace for storage
const POLICY_NS: &str = "00001d00";
const ROLE_NS: &str = "00001d01";
const MAX_KEY_PARTS: usize = 4;

#[derive(Debug)]
pub enum IdentityViewError {
    StateDatabaseError(StateDatabaseError),
    EncodingError(protobuf::ProtobufError),

    UnknownError,
}

impl From<StateDatabaseError> for IdentityViewError {
    fn from(err: StateDatabaseError) -> Self {
        IdentityViewError::StateDatabaseError(err)
    }
}

impl From<protobuf::ProtobufError> for IdentityViewError {
    fn from(err: protobuf::ProtobufError) -> Self {
        IdentityViewError::EncodingError(err)
    }
}

/// Provides a view into global state which translates Role and Policy names
/// into the corresponding addresses, and returns the deserialized values from
/// state.
pub struct IdentityView {
    state_reader: Box<StateReader>,
}

impl IdentityView {
    /// Creates an IdentityView from a given StateReader.
    pub fn new(state_reader: Box<StateReader>) -> Self {
        IdentityView { state_reader }
    }

    /// Returns a single Role by name, if it exists.
    pub fn get_role(&self, name: &str) -> Result<Option<Role>, IdentityViewError> {
        self.get_identity_value::<Role, RoleList>(name, &role_address(name))
    }

    /// Returns all of the Roles under the Identity namespace
    pub fn get_roles(&self) -> Result<Vec<Role>, IdentityViewError> {
        self.get_identity_value_list::<Role, RoleList>(ROLE_NS)
    }

    /// Returns a single Policy by name, if it exists.
    pub fn get_policy(&self, name: &str) -> Result<Option<Policy>, IdentityViewError> {
        self.get_identity_value::<Policy, PolicyList>(name, &policy_address(name))
    }

    /// Returns all of the Policies under the Identity namespace
    pub fn get_policies(&self) -> Result<Vec<Policy>, IdentityViewError> {
        self.get_identity_value_list::<Policy, PolicyList>(POLICY_NS)
    }

    fn get_identity_value<I, L>(
        &self,
        name: &str,
        address: &str,
    ) -> Result<Option<I>, IdentityViewError>
    where
        I: Named,
        L: ProtobufList<I>,
    {
        if !self.state_reader.contains(&address)? {
            return Ok(None);
        }

        self.state_reader
            .get(&address)
            .map_err(IdentityViewError::StateDatabaseError)
            .and_then(|bytes_opt| {
                Ok(if let Some(bytes) = bytes_opt {
                    Some(protobuf::parse_from_bytes::<L>(&bytes)?)
                } else {
                    None
                })
            })
            .and_then(|list_opt| {
                if let Some(list) = list_opt {
                    for item in list.values() {
                        if item.name() == name {
                            return Ok(Some(item.clone()));
                        }
                    }
                }
                // We didn't find the item, so return None
                Ok(None)
            })
    }

    fn get_identity_value_list<I, L>(&self, prefix: &str) -> Result<Vec<I>, IdentityViewError>
    where
        I: Named,
        L: ProtobufList<I>,
    {
        let mut res = Vec::new();
        for state_value in self.state_reader.leaves(Some(prefix))? {
            let (_, bytes) = state_value?;
            let item_list = protobuf::parse_from_bytes::<L>(&bytes)?;
            for item in item_list.values() {
                res.push(item.clone());
            }
        }
        res.sort_by(|a, b| a.name().cmp(b.name()));
        Ok(res)
    }
}

impl From<Box<StateReader>> for IdentityView {
    fn from(state_reader: Box<StateReader>) -> Self {
        IdentityView::new(state_reader)
    }
}

trait ProtobufList<T>: protobuf::Message {
    fn values(&self) -> &[T];
}

impl ProtobufList<Role> for RoleList {
    fn values(&self) -> &[Role] {
        self.get_roles()
    }
}

impl ProtobufList<Policy> for PolicyList {
    fn values(&self) -> &[Policy] {
        self.get_policies()
    }
}

trait Named: Clone {
    fn name(&self) -> &str;
}

impl Named for Role {
    fn name(&self) -> &str {
        self.get_name()
    }
}

impl Named for Policy {
    fn name(&self) -> &str {
        self.get_name()
    }
}

fn role_address(name: &str) -> String {
    let mut address = String::new();
    address.push_str(ROLE_NS);
    address.push_str(
        &name
            .splitn(MAX_KEY_PARTS, '.')
            .chain(repeat(""))
            .enumerate()
            .map(|(i, part)| short_hash(part, if i == 0 { 14 } else { 16 }))
            .take(MAX_KEY_PARTS)
            .collect::<Vec<_>>()
            .join(""),
    );

    address
}

fn policy_address(name: &str) -> String {
    let mut address = String::new();
    address.push_str(POLICY_NS);
    address.push_str(&short_hash(name, 62));
    address
}

fn short_hash(s: &str, length: usize) -> String {
    sha256_digest_str(s)[..length].to_string()
}

#[cfg(test)]
mod tests {
    use super::*;
    use proto::identity::Policy;
    use proto::identity::PolicyList;
    use proto::identity::Policy_Entry;
    use proto::identity::Policy_EntryType;
    use proto::identity::Role;
    use proto::identity::RoleList;

    use protobuf;
    use protobuf::Message;
    use state::StateDatabaseError;
    use state::StateReader;
    use std::collections::HashMap;

    #[test]
    fn addressing() {
        // These addresses were generated using the legacy python code
        assert_eq!(
            "00001d01e0d7826133ad07e3b0c44298fc1c14e3b0c44298fc1c14e3b0c44298fc1c14",
            &role_address("MY_ROLE")
        );
        assert_eq!(
            "00001d00237e86847d59b61cd902a533a1c9701327ed992dfe7ec1996ffc84bc8f0b4e",
            &policy_address("MY_POLICY")
        );
    }

    #[test]
    fn no_roles() {
        let mock_reader = MockStateReader::new(vec![]);
        let identity_view = IdentityView::new(Box::new(mock_reader));

        assert_eq!(None, identity_view.get_role("my_role").unwrap());
        let expect_empty: Vec<Role> = vec![];
        assert_eq!(expect_empty, identity_view.get_roles().unwrap());
    }

    #[test]
    fn get_role_by_name() {
        let mock_reader = MockStateReader::new(vec![
            role_entry("role1", "some_policy"),
            role_entry("role2", "some_other_policy"),
        ]);
        let identity_view = IdentityView::new(Box::new(mock_reader));

        assert_eq!(
            Some(role("role2", "some_other_policy")),
            identity_view.get_role("role2").unwrap()
        );
    }

    #[test]
    fn get_roles() {
        let mock_reader = MockStateReader::new(vec![
            role_entry("role1", "some_policy"),
            role_entry("role2", "some_other_policy"),
        ]);
        let identity_view = IdentityView::new(Box::new(mock_reader));

        assert_eq!(
            vec![
                role("role1", "some_policy"),
                role("role2", "some_other_policy"),
            ],
            identity_view.get_roles().unwrap()
        );
    }

    #[test]
    fn no_policies() {
        let mock_reader = MockStateReader::new(vec![]);
        let identity_view = IdentityView::new(Box::new(mock_reader));

        assert_eq!(None, identity_view.get_policy("my_policy").unwrap());
        let expect_empty: Vec<Policy> = vec![];
        assert_eq!(expect_empty, identity_view.get_policies().unwrap());
    }

    #[test]
    fn get_policy_by_name() {
        let mock_reader = MockStateReader::new(vec![
            policy_entry("policy1", &["some_pubkey"]),
            policy_entry("policy2", &["some_other_pubkey"]),
        ]);
        let identity_view = IdentityView::new(Box::new(mock_reader));

        assert_eq!(
            Some(policy("policy2", &["some_other_pubkey"])),
            identity_view.get_policy("policy2").unwrap()
        );
    }

    #[test]
    fn get_policies() {
        let mock_reader = MockStateReader::new(vec![
            policy_entry("policy1", &["some_pubkey"]),
            policy_entry("policy2", &["some_other_pubkey"]),
        ]);
        let identity_view = IdentityView::new(Box::new(mock_reader));

        assert_eq!(
            vec![
                policy("policy1", &["some_pubkey"]),
                policy("policy2", &["some_other_pubkey"]),
            ],
            identity_view.get_policies().unwrap()
        );
    }

    fn role(name: &str, policy_name: &str) -> Role {
        let mut role = Role::new();
        role.set_name(name.to_string());
        role.set_policy_name(policy_name.to_string());

        role
    }

    fn role_entry(name: &str, policy_name: &str) -> (String, Vec<u8>) {
        let role = role(name, policy_name);
        let mut role_list = RoleList::new();
        role_list.set_roles(protobuf::RepeatedField::from_slice(&[role]));

        (
            role_address(name),
            role_list
                .write_to_bytes()
                .expect("Unable to serialize role"),
        )
    }

    fn policy(name: &str, permits: &[&str]) -> Policy {
        let mut policy = Policy::new();

        policy.set_name(name.to_string());
        policy.set_entries(protobuf::RepeatedField::from_vec(
            permits
                .iter()
                .map(|key| {
                    let mut entry = Policy_Entry::new();
                    entry.set_field_type(Policy_EntryType::PERMIT_KEY);
                    entry.set_key(key.to_string());
                    entry
                })
                .collect(),
        ));

        policy
    }

    fn policy_entry(name: &str, permits: &[&str]) -> (String, Vec<u8>) {
        let policy = policy(name, permits);
        let mut policy_list = PolicyList::new();
        policy_list.set_policies(protobuf::RepeatedField::from_slice(&[policy]));

        (
            policy_address(name),
            policy_list
                .write_to_bytes()
                .expect("Unable to serialize policy"),
        )
    }

    struct MockStateReader {
        state: HashMap<String, Vec<u8>>,
    }

    impl MockStateReader {
        fn new(values: Vec<(String, Vec<u8>)>) -> Self {
            MockStateReader {
                state: values.into_iter().collect(),
            }
        }
    }

    impl StateReader for MockStateReader {
        fn get(&self, address: &str) -> Result<Option<Vec<u8>>, StateDatabaseError> {
            Ok(self.state.get(address).cloned())
        }

        fn contains(&self, address: &str) -> Result<bool, StateDatabaseError> {
            Ok(self.state.contains_key(address))
        }

        fn leaves(
            &self,
            prefix: Option<&str>,
        ) -> Result<
            Box<Iterator<Item = Result<(String, Vec<u8>), StateDatabaseError>>>,
            StateDatabaseError,
        > {
            let iterable: Vec<_> = self
                .state
                .iter()
                .filter(|(key, _)| key.starts_with(prefix.unwrap_or("")))
                .map(|(key, value)| Ok((key.clone().to_string(), value.clone())))
                .collect();

            Ok(Box::new(iterable.into_iter()))
        }
    }
}
