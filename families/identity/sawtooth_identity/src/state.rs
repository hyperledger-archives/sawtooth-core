cfg_if! {
    if #[cfg(target_arch = "wasm32")] {
        use sabre_sdk::ApplyError;
        use sabre_sdk::TransactionContext;

         use protos::identity::{Policy, PolicyList, Role, RoleList};
    } else {
        use sawtooth_sdk::messages::identity::{Policy, PolicyList, Role, RoleList};
        use sawtooth_sdk::processor::handler::ApplyError;
        use sawtooth_sdk::processor::handler::TransactionContext;
    }
}
use crypto::digest::Digest;
use crypto::sha2::Sha256;
use protobuf;
use std::iter::repeat;

pub struct IdentityState<'a> {
    context: &'a mut dyn TransactionContext,
}

impl<'a> IdentityState<'a> {
    pub fn new(context: &'a mut dyn TransactionContext) -> IdentityState {
        IdentityState { context }
    }

    const MAX_KEY_PARTS: usize = 4;
    const _FIRST_ADDRESS_PART_SIZE: usize = 14;
    const _ADDRESS_PART_SIZE: usize = 16;
    const POLICY_NS: &'a str = "00001d00";
    const ROLE_NS: &'a str = "00001d01";

    pub fn get_policy_list(&mut self, name: &str) -> Result<Option<PolicyList>, ApplyError> {
        let address = self.get_policy_address(name);
        let policy_data = self.get_state_data(&address)?;
        match policy_data {
            Some(data) => Ok(Some(unpack_data(&data)?)),
            None => Ok(None),
        }
    }

    pub fn get_role_list(&mut self, name: &str) -> Result<Option<RoleList>, ApplyError> {
        let address = self.get_role_address(name);
        let role_data = self.get_state_data(&address)?;
        match role_data {
            Some(data) => Ok(Some(unpack_data(&data)?)),
            None => Ok(None),
        }
    }

    fn get_state_data(&mut self, address: &str) -> Result<Option<Vec<u8>>, ApplyError> {
        self.context.get_state_entry(address).map_err(|err| {
            warn!("Invalid transaction: Failed to load state: {:?}", err);
            ApplyError::InvalidTransaction(format!("Failed to load state: {:?}", err))
        })
    }

    pub fn set_policy(&mut self, new_policy: Policy) -> Result<(), ApplyError> {
        let policy_name = new_policy.name.clone();

        let mut policy_list = match self.get_policy_list(&policy_name)? {
            Some(policy_list) => policy_list,
            None => PolicyList::new(),
        };

        if let Some((i, _)) = policy_list
            .get_policies()
            .iter()
            .enumerate()
            .find(|(_i, policy)| policy.get_name() == policy_name)
        {
            // If policy with same name exists, replace old policy with new policy
            let policy_slice = policy_list.policies.as_mut_slice();
            policy_slice[i] = new_policy;
        } else {
            // If policy with same name does not exist, insert new policy
            policy_list.policies.push(new_policy);
            policy_list
                .policies
                .sort_unstable_by(|p1, p2| p1.get_name().cmp(p2.get_name()));
        }

        let address = self.get_policy_address(&policy_name);
        let data = protobuf::Message::write_to_bytes(&policy_list).map_err(|err| {
            ApplyError::InternalError(format!("Failed to serialize PolicyList: {:?}", err))
        })?;

        self.set_state(&policy_name, &address, data)
    }

    pub fn set_role(&mut self, new_role: Role) -> Result<(), ApplyError> {
        let role_name = new_role.name.clone();
        let mut role_list = match self.get_role_list(&role_name)? {
            Some(role_list) => role_list,
            None => RoleList::new(),
        };

        if let Some((i, _)) = role_list
            .get_roles()
            .iter()
            .enumerate()
            .find(|(_i, role)| role.get_name() == role_name)
        {
            // If role with same name exists, replace old role with new role
            let role_slice = role_list.roles.as_mut_slice();
            role_slice[i] = new_role;
        } else {
            // If role with same name does not exist, insert new role
            role_list.roles.push(new_role);
            role_list
                .roles
                .sort_unstable_by(|r1, r2| r1.get_name().cmp(r2.get_name()));
        }

        let address = self.get_role_address(&role_name);
        let data = protobuf::Message::write_to_bytes(&role_list).map_err(|err| {
            ApplyError::InternalError(format!("Failed to serialize RoleList: {:?}", err))
        })?;

        self.set_state(&role_name, &address, data)
    }

    fn set_state(&mut self, name: &str, address: &str, data: Vec<u8>) -> Result<(), ApplyError> {
        self.context
            .set_state_entry(address.into(), data)
            .map_err(|_err| {
                warn!("Failed to set {} at {}", name, address);
                ApplyError::InternalError(format!("Unable to set {}", name))
            })?;
        debug!("Set: \n{:?}", name);

        #[cfg(not(target_arch = "wasm32"))]
        self.context
            .add_event(
                "identity/update".to_string(),
                vec![("updated".to_string(), name.to_string())],
                &[],
            )
            .map_err(|_err| {
                warn!("Failed to add event {}", name);
                ApplyError::InternalError(format!("Failed to add event {}", name))
            })?;
        Ok(())
    }

    fn short_hash(&mut self, s: &str, length: usize) -> String {
        let mut sha = Sha256::new();
        sha.input(s.as_bytes());
        sha.result_str()[..length].to_string()
    }

    fn get_role_address(&mut self, name: &str) -> String {
        let mut address = String::new();
        address.push_str(IdentityState::ROLE_NS);
        address.push_str(
            &name
                .splitn(IdentityState::MAX_KEY_PARTS, '.')
                .chain(repeat(""))
                .enumerate()
                .map(|(i, part)| self.short_hash(part, if i == 0 { 14 } else { 16 }))
                .take(IdentityState::MAX_KEY_PARTS)
                .collect::<Vec<_>>()
                .join(""),
        );

        address
    }

    fn get_policy_address(&mut self, name: &str) -> String {
        let mut address = String::new();
        address.push_str(IdentityState::POLICY_NS);
        address.push_str(&self.short_hash(name, 62));
        address
    }
}

fn unpack_data<T>(data: &[u8]) -> Result<T, ApplyError>
where
    T: protobuf::Message,
{
    protobuf::parse_from_bytes(&data).map_err(|err| {
        warn!(
            "Invalid transaction: Failed to unmarshal IdentityTransaction: {:?}",
            err
        );
        ApplyError::InvalidTransaction(format!(
            "Failed to unmarshal IdentityTransaction: {:?}",
            err
        ))
    })
}
