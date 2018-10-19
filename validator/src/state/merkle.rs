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

use std::collections::BTreeMap;
use std::collections::HashMap;
use std::collections::HashSet;
use std::collections::VecDeque;
use std::io::Cursor;

use cbor;
use cbor::decoder::GenericDecoder;
use cbor::encoder::GenericEncoder;
use cbor::value::Bytes;
use cbor::value::Key;
use cbor::value::Text;
use cbor::value::Value;

use hashlib::sha512_digest_bytes;

use protobuf;
use protobuf::Message;

use database::database::DatabaseError;
use database::lmdb::DatabaseReader;
use database::lmdb::LmdbDatabase;
use database::lmdb::LmdbDatabaseWriter;

use proto::merkle::ChangeLogEntry;
use proto::merkle::ChangeLogEntry_Successor;

use state::error::StateDatabaseError;
use state::StateReader;

const TOKEN_SIZE: usize = 2;

pub const CHANGE_LOG_INDEX: &str = "change_log";
pub const DUPLICATE_LOG_INDEX: &str = "duplicate_log";
pub const INDEXES: [&'static str; 2] = [CHANGE_LOG_INDEX, DUPLICATE_LOG_INDEX];

/// Merkle Database
#[derive(Clone)]
pub struct MerkleDatabase {
    root_hash: String,
    db: LmdbDatabase,
    root_node: Node,
}

impl MerkleDatabase {
    /// Constructs a new MerkleDatabase, backed by a given Database
    ///
    /// An optional starting merkle root may be provided.
    pub fn new(db: LmdbDatabase, merkle_root: Option<&str>) -> Result<Self, StateDatabaseError> {
        let root_hash = merkle_root.map_or_else(|| initialize_db(&db), |s| Ok(s.into()))?;
        let root_node = get_node_by_hash(&db, &root_hash)?;

        Ok(MerkleDatabase {
            root_hash,
            root_node,
            db,
        })
    }

    /// Prunes nodes that are no longer needed under a given state root
    /// Returns a list of addresses that were deleted
    pub fn prune(db: &LmdbDatabase, merkle_root: &str) -> Result<Vec<String>, StateDatabaseError> {
        let root_bytes = ::hex::decode(merkle_root).map_err(|_| {
            StateDatabaseError::InvalidHash(format!("{} is not a valid hash", merkle_root))
        })?;
        let mut db_writer = db.writer()?;
        let change_log = get_change_log(&db_writer, &root_bytes)?;

        if change_log.is_none() {
            // There's no change log for this entry
            return Ok(vec![]);
        }

        let mut change_log = change_log.unwrap();
        let removed_addresses = if change_log.get_successors().len() > 1 {
            // Currently, we don't clean up a parent with multiple successors
            vec![]
        } else if change_log.get_successors().is_empty() {
            // deleting the tip of a trie lineage

            let (deletion_candidates, duplicates): (Vec<Vec<u8>>, Vec<Vec<u8>>) =
                MerkleDatabase::remove_duplicate_hashes(
                    &mut db_writer,
                    change_log.take_additions(),
                )?;

            for hash in &deletion_candidates {
                let hash_hex = ::hex::encode(hash);
                delete_ignore_missing(&mut db_writer, hash_hex.as_bytes())?
            }

            for hash in &duplicates {
                decrement_ref_count(&mut db_writer, hash)?;
            }

            db_writer.index_delete(CHANGE_LOG_INDEX, &root_bytes)?;
            let parent_root_bytes = &change_log.get_parent();

            if let Some(ref mut parent_change_log) =
                get_change_log(&db_writer, parent_root_bytes)?.as_mut()
            {
                let successors = parent_change_log.take_successors();
                let new_successors = successors
                    .into_iter()
                    .filter(|successor| root_bytes != successor.get_successor())
                    .collect::<Vec<_>>();
                parent_change_log.set_successors(protobuf::RepeatedField::from_vec(new_successors));

                write_change_log(&mut db_writer, parent_root_bytes, &parent_change_log)?;
            }

            deletion_candidates.into_iter().collect()
        } else {
            // deleting a parent
            let mut successor = change_log.take_successors().pop().unwrap();

            let (deletion_candidates, duplicates): (Vec<Vec<u8>>, Vec<Vec<u8>>) =
                MerkleDatabase::remove_duplicate_hashes(
                    &mut db_writer,
                    successor.take_deletions(),
                )?;

            for hash in &deletion_candidates {
                let hash_hex = ::hex::encode(hash);
                delete_ignore_missing(&mut db_writer, hash_hex.as_bytes())?
            }

            for hash in &duplicates {
                decrement_ref_count(&mut db_writer, hash)?;
            }

            db_writer.index_delete(CHANGE_LOG_INDEX, &root_bytes)?;

            deletion_candidates.into_iter().collect()
        };

        db_writer.commit()?;
        Ok(removed_addresses.iter().map(::hex::encode).collect())
    }

    fn remove_duplicate_hashes(
        db_writer: &mut LmdbDatabaseWriter,
        deletions: protobuf::RepeatedField<Vec<u8>>,
    ) -> Result<(Vec<Vec<u8>>, Vec<Vec<u8>>), StateDatabaseError> {
        let (deletion_candidates, decrements): (Vec<Vec<u8>>, Vec<Vec<u8>>) =
            deletions.into_iter().partition(|key| {
                if let Ok(count) = get_ref_count(db_writer, &key) {
                    count == 0
                } else {
                    false
                }
            });

        Ok((deletion_candidates, decrements))
    }

    /// Returns the current merkle root for this MerkleDatabase
    pub fn get_merkle_root(&self) -> String {
        self.root_hash.clone()
    }

    /// Sets the current merkle root for this MerkleDatabase
    pub fn set_merkle_root<S: Into<String>>(
        &mut self,
        merkle_root: S,
    ) -> Result<(), StateDatabaseError> {
        let new_root = merkle_root.into();
        self.root_node = get_node_by_hash(&self.db, &new_root)?;
        self.root_hash = new_root;
        Ok(())
    }

    /// Sets the given data at the given address.
    ///
    /// Returns a Result with the new merkle root hash, or an error if the
    /// address is not in the tree.
    ///
    /// Note, continued calls to get, without changing the merkle root to the
    /// result of this function, will not retrieve the results provided here.
    pub fn set(&self, address: &str, data: &[u8]) -> Result<String, StateDatabaseError> {
        let mut updates = HashMap::with_capacity(1);
        updates.insert(address.to_string(), data.to_vec());
        self.update(&updates, &[], false)
    }

    /// Deletes the value at the given address.
    ///
    /// Returns a Result with the new merkle root hash, or an error if the
    /// address is not in the tree.
    ///
    /// Note, continued calls to get, without changing the merkle root to the
    /// result of this function, will still retrieve the data at the address
    /// provided
    pub fn delete(&self, address: &str) -> Result<String, StateDatabaseError> {
        self.update(&HashMap::with_capacity(0), &[address.to_string()], false)
    }

    /// Updates the tree with multiple changes.  Applies both set and deletes,
    /// as given.
    ///
    /// If the flag `is_virtual` is set, the values are not written to the
    /// underlying database.
    ///
    /// Returns a Result with the new root hash.
    pub fn update(
        &self,
        set_items: &HashMap<String, Vec<u8>>,
        delete_items: &[String],
        is_virtual: bool,
    ) -> Result<String, StateDatabaseError> {
        let mut path_map = HashMap::new();

        let mut deletions = HashSet::new();

        for (set_address, set_value) in set_items {
            let tokens = tokenize_address(set_address);
            let mut set_path_map = self.get_path_by_tokens(&tokens, false)?;

            {
                let node = set_path_map
                    .get_mut(set_address)
                    .expect("Path map not correctly generated");
                node.value = Some(set_value.to_vec());
            }
            path_map.extend(set_path_map);
        }

        for del_address in delete_items.iter() {
            let tokens = tokenize_address(del_address);
            let del_path_map = self.get_path_by_tokens(&tokens, true)?;
            path_map.extend(del_path_map);
        }

        for del_address in delete_items.iter() {
            path_map.remove(del_address);
            let (mut parent_address, mut path_branch) = parent_and_branch(del_address);
            while parent_address != "" {
                let remove_parent = {
                    let parent_node = path_map
                        .get_mut(parent_address)
                        .expect("Path map not correctly generated");

                    if let Some(old_hash_key) = parent_node.children.remove(path_branch) {
                        deletions.insert(old_hash_key);
                    }

                    parent_node.children.is_empty()
                };

                if remove_parent {
                    // empty node delete it.
                    path_map.remove(parent_address);
                } else {
                    // found a node that is not empty no need to continue
                    break;
                }

                let (next_parent, next_branch) = parent_and_branch(parent_address);
                parent_address = next_parent;
                path_branch = next_branch;

                if parent_address == "" {
                    let parent_node = path_map
                        .get_mut(parent_address)
                        .expect("Path map not correctly generated");

                    if let Some(old_hash_key) = parent_node.children.remove(path_branch) {
                        deletions.insert(old_hash_key);
                    }
                }
            }
        }

        let mut sorted_paths: Vec<_> = path_map.keys().cloned().collect();
        // Sort by longest to shortest
        sorted_paths.sort_by(|a, b| b.len().cmp(&a.len()));

        // initializing this to empty, to make the compiler happy
        let mut key_hash = Vec::with_capacity(0);
        let mut batch = Vec::with_capacity(sorted_paths.len());
        for path in sorted_paths {
            let node = path_map
                .remove(&path)
                .expect("Path map keys are out of sink");
            let (hash_key, packed) = encode_and_hash(node)?;
            key_hash = hash_key.clone();

            if path != "" {
                let (parent_address, path_branch) = parent_and_branch(&path);
                let mut parent = path_map
                    .get_mut(parent_address)
                    .expect("Path map not correctly generated");
                if let Some(old_hash_key) = parent
                    .children
                    .insert(path_branch.to_string(), ::hex::encode(hash_key.clone()))
                {
                    deletions.insert(old_hash_key);
                }
            }

            batch.push((hash_key, packed));
        }

        if !is_virtual {
            let deletions: Vec<Vec<u8>> = deletions
                .iter()
                // We expect this to be hex, since we generated it
                .map(|s| ::hex::decode(s).expect("Improper hex"))
                .collect();
            self.store_changes(&key_hash, &batch, &deletions)?;
        }

        Ok(::hex::encode(key_hash))
    }

    /// Puts all the items into the database.
    fn store_changes(
        &self,
        successor_root_hash: &[u8],
        batch: &[(Vec<u8>, Vec<u8>)],
        deletions: &[Vec<u8>],
    ) -> Result<(), StateDatabaseError> {
        let mut db_writer = self.db.writer()?;

        // We expect this to be hex, since we generated it
        let root_hash_bytes = ::hex::decode(&self.root_hash).expect("Improper hex");

        for &(ref key, ref value) in batch {
            match db_writer.put(::hex::encode(key).as_bytes(), &value) {
                Ok(_) => continue,
                Err(DatabaseError::DuplicateEntry) => {
                    increment_ref_count(&mut db_writer, key)?;
                }
                Err(err) => return Err(StateDatabaseError::from(err)),
            }
        }

        let mut current_change_log = get_change_log(&db_writer, &root_hash_bytes)?;
        if let Some(change_log) = current_change_log.as_mut() {
            let mut successors = change_log.mut_successors();
            let mut successor = ChangeLogEntry_Successor::new();
            successor.set_successor(Vec::from(successor_root_hash));
            successor.set_deletions(protobuf::RepeatedField::from_slice(deletions));
            successors.push(successor);
        }

        let mut next_change_log = ChangeLogEntry::new();
        next_change_log.set_parent(root_hash_bytes.clone());
        next_change_log.set_additions(protobuf::RepeatedField::from(
            batch
                .iter()
                .map(|&(ref hash, _)| hash.clone())
                .collect::<Vec<Vec<u8>>>(),
        ));

        if current_change_log.is_some() {
            write_change_log(
                &mut db_writer,
                &root_hash_bytes,
                &current_change_log.unwrap(),
            )?;
        }
        write_change_log(&mut db_writer, successor_root_hash, &next_change_log)?;

        db_writer.commit()?;
        Ok(())
    }

    fn get_by_address(&self, address: &str) -> Result<Node, StateDatabaseError> {
        let tokens = tokenize_address(address);

        // There's probably a better way to do this than a clone
        let mut node = self.root_node.clone();

        for token in tokens.iter() {
            node = match node.children.get(&token.to_string()) {
                None => {
                    return Err(StateDatabaseError::NotFound(format!(
                        "invalid address {} from root {}",
                        address, self.root_hash
                    )))
                }
                Some(child_hash) => get_node_by_hash(&self.db, child_hash)?,
            }
        }
        Ok(node)
    }

    fn get_path_by_tokens(
        &self,
        tokens: &[&str],
        strict: bool,
    ) -> Result<HashMap<String, Node>, StateDatabaseError> {
        let mut nodes = HashMap::new();

        let mut path = String::new();
        nodes.insert(path.clone(), self.root_node.clone());

        let mut new_branch = false;

        for token in tokens {
            let node = {
                // this is safe to unwrap, because we've just inserted the path in the previous loop
                let child_address = &nodes[&path].children.get(&token.to_string());
                if !new_branch && child_address.is_some() {
                    get_node_by_hash(&self.db, child_address.unwrap())?
                } else {
                    if strict {
                        return Err(StateDatabaseError::NotFound(format!(
                            "invalid address {} from root {}",
                            tokens.join(""),
                            self.root_hash
                        )));
                    } else {
                        new_branch = true;
                        Node::default()
                    }
                }
            };

            path.push_str(token);
            nodes.insert(path.clone(), node);
        }
        Ok(nodes)
    }
}

impl StateReader for MerkleDatabase {
    /// Returns true if the given address exists in the MerkleDatabase;
    /// false, otherwise.
    fn contains(&self, address: &str) -> Result<bool, StateDatabaseError> {
        match self.get_by_address(address) {
            Ok(_) => Ok(true),
            Err(StateDatabaseError::NotFound(_)) => Ok(false),
            Err(err) => Err(err),
        }
    }

    /// Returns the data for a given address, if they exist at that node.  If
    /// not, returns None.  Will return an StateDatabaseError::NotFound, if the
    /// given address is not in the tree
    fn get(&self, address: &str) -> Result<Option<Vec<u8>>, StateDatabaseError> {
        Ok(self.get_by_address(address)?.value)
    }

    fn leaves(
        &self,
        prefix: Option<&str>,
    ) -> Result<
        Box<Iterator<Item = Result<(String, Vec<u8>), StateDatabaseError>>>,
        StateDatabaseError,
    > {
        Ok(Box::new(MerkleLeafIterator::new(self.clone(), prefix)?))
    }
}

/// A MerkleLeafIterator is fixed to iterate over the state address/value pairs
/// the merkle root hash at the time of its creation.
pub struct MerkleLeafIterator {
    merkle_db: MerkleDatabase,
    visited: VecDeque<(String, Node)>,
}

impl MerkleLeafIterator {
    fn new(merkle_db: MerkleDatabase, prefix: Option<&str>) -> Result<Self, StateDatabaseError> {
        let path = prefix.unwrap_or("");

        let mut visited = VecDeque::new();
        let initial_node = merkle_db.get_by_address(path)?;
        visited.push_front((path.to_string(), initial_node));

        Ok(MerkleLeafIterator { merkle_db, visited })
    }
}

impl Iterator for MerkleLeafIterator {
    type Item = Result<(String, Vec<u8>), StateDatabaseError>;

    fn next(&mut self) -> Option<Self::Item> {
        if self.visited.is_empty() {
            return None;
        }

        loop {
            if let Some((path, node)) = self.visited.pop_front() {
                if node.value.is_some() {
                    return Some(Ok((path, node.value.unwrap())));
                }

                // Reverse the list, such that we have an in-order traversal of the
                // children, based on the natural path order.
                for (child_path, hash_key) in node.children.iter().rev() {
                    let child = match get_node_by_hash(&self.merkle_db.db, hash_key) {
                        Ok(node) => node,
                        Err(err) => return Some(Err(err)),
                    };
                    let mut child_address = path.clone();
                    child_address.push_str(child_path);
                    self.visited.push_front((child_address, child));
                }
            } else {
                return None;
            }
        }
    }
}

/// Initializes a database with an empty Trie
fn initialize_db(db: &LmdbDatabase) -> Result<String, StateDatabaseError> {
    let (hash, packed) = encode_and_hash(Node::default())?;

    let mut db_writer = db.writer()?;
    let hex_hash = ::hex::encode(hash);
    // Ignore ref counts for the default, empty tree
    db_writer.overwrite(hex_hash.as_bytes(), &packed)?;
    db_writer.commit()?;

    Ok(hex_hash)
}

/// Returns the change log entry for a given root hash.
fn get_change_log<R>(
    db_reader: &R,
    root_hash: &[u8],
) -> Result<Option<ChangeLogEntry>, StateDatabaseError>
where
    R: DatabaseReader,
{
    let log_bytes = db_reader.index_get(CHANGE_LOG_INDEX, root_hash)?;

    Ok(match log_bytes {
        Some(bytes) => Some(protobuf::parse_from_bytes(&bytes)?),
        None => None,
    })
}

/// Writes the given change log entry to the database
fn write_change_log(
    db_writer: &mut LmdbDatabaseWriter,
    root_hash: &[u8],
    change_log: &ChangeLogEntry,
) -> Result<(), StateDatabaseError> {
    Ok(db_writer.index_put(CHANGE_LOG_INDEX, root_hash, &change_log.write_to_bytes()?)?)
}

fn increment_ref_count(
    db_writer: &mut LmdbDatabaseWriter,
    key: &[u8],
) -> Result<u64, StateDatabaseError> {
    let ref_count = get_ref_count(db_writer, key)?;

    db_writer.index_put(DUPLICATE_LOG_INDEX, key, &to_bytes(ref_count + 1))?;

    Ok(ref_count)
}

fn decrement_ref_count(
    db_writer: &mut LmdbDatabaseWriter,
    key: &[u8],
) -> Result<u64, StateDatabaseError> {
    let count = get_ref_count(db_writer, key)?;
    Ok(if count == 1 {
        db_writer.index_delete(DUPLICATE_LOG_INDEX, key)?;
        0
    } else {
        db_writer.index_put(DUPLICATE_LOG_INDEX, key, &to_bytes(count - 1))?;
        count - 1
    })
}

fn get_ref_count(
    db_writer: &mut LmdbDatabaseWriter,
    key: &[u8],
) -> Result<u64, StateDatabaseError> {
    Ok(
        if let Some(ref_count) = db_writer.index_get(DUPLICATE_LOG_INDEX, key)? {
            from_bytes(ref_count)
        } else {
            0
        },
    )
}

fn to_bytes(num: u64) -> [u8; 8] {
    unsafe { ::std::mem::transmute(num.to_le()) }
}

fn from_bytes(bytes: Vec<u8>) -> u64 {
    let mut num_bytes = [0u8; 8];
    num_bytes.copy_from_slice(&bytes);
    u64::from_le(unsafe { ::std::mem::transmute(num_bytes) })
}

/// This delete ignores any MDB_NOTFOUND errors
fn delete_ignore_missing(
    db_writer: &mut LmdbDatabaseWriter,
    key: &[u8],
) -> Result<(), StateDatabaseError> {
    match db_writer.delete(key) {
        Err(DatabaseError::WriterError(ref s))
            if s == "MDB_NOTFOUND: No matching key/data pair found" =>
        {
            // This can be ignored, as the record doesn't exist
            debug!(
                "Attempting to delete a missing entry: {}",
                ::hex::encode(key)
            );
            Ok(())
        }
        Err(err) => Err(StateDatabaseError::DatabaseError(err)),
        Ok(_) => Ok(()),
    }
}
/// Encodes the given node, and returns the hash of the bytes.
fn encode_and_hash(node: Node) -> Result<(Vec<u8>, Vec<u8>), StateDatabaseError> {
    let packed = node.into_bytes()?;
    let hash = hash(&packed);
    Ok((hash, packed))
}

/// Given a path, split it into its parent's path and the specific branch for
/// this path, such that the following assertion is true:
///
/// ```
/// let (parent_path, branch) = parent_and_branch(some_path);
/// let mut path = String::new();
/// path.push(parent_path);
/// path.push(branch);
/// assert_eq!(some_path, &path);
/// ```
fn parent_and_branch(path: &str) -> (&str, &str) {
    let parent_address = if !path.is_empty() {
        &path[..path.len() - TOKEN_SIZE]
    } else {
        ""
    };

    let path_branch = if !path.is_empty() {
        &path[(path.len() - TOKEN_SIZE)..]
    } else {
        ""
    };

    (parent_address, path_branch)
}

/// Splits an address into tokens
fn tokenize_address(address: &str) -> Box<[&str]> {
    let mut tokens: Vec<&str> = Vec::with_capacity(address.len() / TOKEN_SIZE);
    let mut i = 0;
    while i < address.len() {
        tokens.push(&address[i..i + TOKEN_SIZE]);
        i += TOKEN_SIZE;
    }
    tokens.into_boxed_slice()
}

/// Fetch a node by its hash
fn get_node_by_hash(db: &LmdbDatabase, hash: &str) -> Result<Node, StateDatabaseError> {
    match db.reader()?.get(hash.as_bytes()) {
        Some(bytes) => Node::from_bytes(&bytes),
        None => Err(StateDatabaseError::NotFound(hash.to_string())),
    }
}

/// Internal Node structure of the Radix tree
#[derive(Default, Debug, PartialEq, Clone)]
struct Node {
    value: Option<Vec<u8>>,
    children: BTreeMap<String, String>,
}

impl Node {
    /// Consumes this node and serializes it to bytes
    fn into_bytes(self) -> Result<Vec<u8>, StateDatabaseError> {
        let mut e = GenericEncoder::new(Cursor::new(Vec::new()));

        let mut map = BTreeMap::new();
        map.insert(
            Key::Text(Text::Text("v".to_string())),
            match self.value {
                Some(bytes) => Value::Bytes(Bytes::Bytes(bytes)),
                None => Value::Null,
            },
        );

        let children = self
            .children
            .into_iter()
            .map(|(k, v)| {
                (
                    Key::Text(Text::Text(k.to_string())),
                    Value::Text(Text::Text(v.to_string())),
                )
            }).collect();

        map.insert(Key::Text(Text::Text("c".to_string())), Value::Map(children));

        e.value(&Value::Map(map))?;

        Ok(e.into_inner().into_writer().into_inner())
    }

    /// Deserializes the given bytes to a Node
    fn from_bytes(bytes: &[u8]) -> Result<Node, StateDatabaseError> {
        let input = Cursor::new(bytes);
        let mut decoder = GenericDecoder::new(cbor::Config::default(), input);
        let decoder_value = decoder.value()?;
        let (val, children_raw) = match decoder_value {
            Value::Map(mut root_map) => (
                root_map.remove(&Key::Text(Text::Text("v".to_string()))),
                root_map.remove(&Key::Text(Text::Text("c".to_string()))),
            ),
            _ => return Err(StateDatabaseError::InvalidRecord),
        };

        let value = match val {
            Some(Value::Bytes(Bytes::Bytes(bytes))) => Some(bytes),
            Some(Value::Null) => None,
            _ => return Err(StateDatabaseError::InvalidRecord),
        };

        let children = match children_raw {
            Some(Value::Map(mut child_map)) => {
                let mut result = BTreeMap::new();
                for (k, v) in child_map {
                    result.insert(key_to_string(k)?, text_to_string(v)?);
                }
                result
            }
            None => BTreeMap::new(),
            _ => return Err(StateDatabaseError::InvalidRecord),
        };

        Ok(Node { value, children })
    }
}

/// Converts a CBOR Key to its String content
fn key_to_string(key_val: Key) -> Result<String, StateDatabaseError> {
    match key_val {
        Key::Text(Text::Text(s)) => Ok(s),
        _ => Err(StateDatabaseError::InvalidRecord),
    }
}

/// Converts a CBOR Text Value to its String content
fn text_to_string(text_val: Value) -> Result<String, StateDatabaseError> {
    match text_val {
        Value::Text(Text::Text(s)) => Ok(s),
        _ => Err(StateDatabaseError::InvalidRecord),
    }
}

/// Creates a hash of the given bytes
fn hash(input: &[u8]) -> Vec<u8> {
    let bytes = sha512_digest_bytes(input);
    let (hash, _rest) = bytes.split_at(bytes.len() / 2);
    hash.to_vec()
}

#[cfg(test)]
mod tests {
    use super::*;
    use database::database::DatabaseError;
    use database::lmdb::DatabaseReader;
    use database::lmdb::LmdbContext;
    use database::lmdb::LmdbDatabase;
    use proto::merkle::ChangeLogEntry;

    use protobuf;
    use rand::{seq, thread_rng};
    use std::env;
    use std::fs::remove_file;
    use std::panic;
    use std::path::Path;
    use std::str::from_utf8;
    use std::thread;

    #[test]
    fn node_serialize() {
        let n = Node {
            value: Some(b"hello".to_vec()),
            children: vec![("ab".to_string(), "123".to_string())]
                .into_iter()
                .collect(),
        };

        let packed = n
            .into_bytes()
            .unwrap()
            .iter()
            .map(|b| format!("{:x}", b))
            .collect::<Vec<_>>()
            .join("");
        // This expected output was generated using the python structures
        let output = "a26163a16261626331323361764568656c6c6f";

        assert_eq!(output, packed);
    }

    #[test]
    fn node_deserialize() {
        let packed =
            ::hex::decode("a26163a162303063616263617647676f6f64627965").expect("improper hex");

        let unpacked = Node::from_bytes(&packed).unwrap();
        assert_eq!(
            Node {
                value: Some(b"goodbye".to_vec()),
                children: vec![("00".to_string(), "abc".to_string())]
                    .into_iter()
                    .collect(),
            },
            unpacked
        );
    }

    #[test]
    fn node_roundtrip() {
        let n = Node {
            value: Some(b"hello".to_vec()),
            children: vec![("ab".to_string(), "123".to_string())]
                .into_iter()
                .collect(),
        };

        let packed = n.into_bytes().unwrap();
        let unpacked = Node::from_bytes(&packed).unwrap();

        assert_eq!(
            Node {
                value: Some(b"hello".to_vec()),
                children: vec![("ab".to_string(), "123".to_string())]
                    .into_iter()
                    .collect(),
            },
            unpacked
        )
    }

    #[test]
    fn merkle_trie_root_advance() {
        run_test(|merkle_path| {
            let db = make_lmdb(&merkle_path);
            let mut merkle_db = MerkleDatabase::new(db.clone(), None).unwrap();

            let orig_root = merkle_db.get_merkle_root();
            let orig_root_bytes = &::hex::decode(orig_root.clone()).unwrap();

            {
                // check that there is no ChangeLogEntry for the initial root
                let reader = db.reader().unwrap();
                assert!(
                    reader
                        .index_get(CHANGE_LOG_INDEX, orig_root_bytes)
                        .expect("A database error occurred")
                        .is_none()
                );
            }

            let new_root = merkle_db.set("abcd", "data_value".as_bytes()).unwrap();
            let new_root_bytes = &::hex::decode(new_root.clone()).unwrap();

            assert_eq!(merkle_db.get_merkle_root(), orig_root, "Incorrect root");
            assert_ne!(orig_root, new_root, "root was not changed");
            assert!(
                !merkle_db.contains("abcd").unwrap(),
                "Should not contain the value"
            );

            let change_log: ChangeLogEntry = {
                // check that we have a change log entry for the new root
                let reader = db.reader().unwrap();
                let entry_bytes = &reader
                    .index_get(CHANGE_LOG_INDEX, new_root_bytes)
                    .expect("A database error occurred")
                    .expect("Did not return a change log entry");
                protobuf::parse_from_bytes(entry_bytes).expect("Failed to parse change log entry")
            };

            assert_eq!(orig_root_bytes, &change_log.get_parent());
            assert_eq!(3, change_log.get_additions().len());
            assert_eq!(0, change_log.get_successors().len());

            merkle_db.set_merkle_root(new_root.clone()).unwrap();
            assert_eq!(merkle_db.get_merkle_root(), new_root, "Incorrect root");

            assert_value_at_address(&merkle_db, "abcd", "data_value");
        })
    }

    #[test]
    fn merkle_trie_delete() {
        run_test(|merkle_path| {
            let mut merkle_db = make_db(&merkle_path);

            let new_root = merkle_db.set("1234", "deletable".as_bytes()).unwrap();
            merkle_db.set_merkle_root(new_root).unwrap();
            assert_value_at_address(&merkle_db, "1234", "deletable");

            // deleting an unknown key should return an error
            assert!(merkle_db.delete("barf").is_err());

            let del_root = merkle_db.delete("1234").unwrap();

            // del_root hasn't been set yet, so address should still have value
            assert_value_at_address(&merkle_db, "1234", "deletable");
            merkle_db.set_merkle_root(del_root).unwrap();
            assert!(!merkle_db.contains("1234").unwrap());
        })
    }

    #[test]
    fn merkle_trie_update() {
        run_test(|merkle_path| {
            let mut merkle_db = make_db(&merkle_path);
            let init_root = merkle_db.get_merkle_root();

            let key_hashes = (0..1000)
                .map(|i| {
                    let key = format!("{:016x}", i);
                    let hash = hex_hash(key.as_bytes());
                    (key, hash)
                }).collect::<Vec<_>>();

            let mut values = HashMap::new();
            for &(ref key, ref hashed) in key_hashes.iter() {
                let new_root = merkle_db.set(&hashed, key.as_bytes()).unwrap();
                values.insert(hashed.clone(), key.to_string());
                merkle_db.set_merkle_root(new_root).unwrap();
            }

            assert_ne!(init_root, merkle_db.get_merkle_root());

            let mut rng = thread_rng();
            let mut set_items = HashMap::new();
            // Perform some updates on the lower keys
            for i in seq::sample_iter(&mut rng, 0..500, 50).unwrap() {
                let hash_key = hex_hash(format!("{:016x}", i).as_bytes());
                set_items.insert(hash_key.clone(), "5.0".as_bytes().to_vec());
                values.insert(hash_key.clone(), "5.0".to_string());
            }

            // perform some deletions on the upper keys
            let delete_items = seq::sample_iter(&mut rng, 500..1000, 50)
                .unwrap()
                .into_iter()
                .map(|i| hex_hash(format!("{:016x}", i).as_bytes()))
                .collect::<Vec<String>>();

            for hash in delete_items.iter() {
                values.remove(hash);
            }

            let virtual_root = merkle_db.update(&set_items, &delete_items, true).unwrap();

            // virtual root shouldn't match actual contents of tree
            assert!(merkle_db.set_merkle_root(virtual_root.clone()).is_err());

            let actual_root = merkle_db.update(&set_items, &delete_items, false).unwrap();
            // the virtual root should be the same as the actual root
            assert_eq!(virtual_root, actual_root);
            assert_ne!(actual_root, merkle_db.get_merkle_root());

            merkle_db.set_merkle_root(actual_root).unwrap();

            for (address, value) in values {
                assert_value_at_address(&merkle_db, &address, &value);
            }

            for address in delete_items {
                assert!(merkle_db.get(&address).is_err());
            }
        })
    }

    #[test]
    /// This test is similar to the update test except that it will ensure that
    /// there are no index errors in path_map within update function in case
    /// there are addresses within set_items & delete_items which have a common
    /// prefix (of any length).
    ///
    /// A Merkle trie is created with some initial values which is then updated
    /// (set & delete).
    fn merkle_trie_update_same_address_space() {
        run_test(|merkle_path| {
            let mut merkle_db = make_db(merkle_path);
            let init_root = merkle_db.get_merkle_root();
            let key_hashes = vec![
                // matching prefix e55420
                (
                    "asdfg",
                    "e5542002d3e2892516fa461cde69e05880609fbad3d38ab69435a189e126de672b620c",
                ),
                (
                    "qwert",
                    "c946ee72d38b8c51328f1a5f31eb5bd3300362ad0ca69dab54eff996775c7069216bda",
                ),
                (
                    "zxcvb",
                    "487a6a63c71c9b7b63146ef68858e5d010b4978fd70dda0404d4fad5e298ccc9a560eb",
                ),
                // matching prefix e55420
                (
                    "yuiop",
                    "e55420c026596ee643e26fd93927249ea28fb5f359ddbd18bc02562dc7e8dbc93e89b9",
                ),
                (
                    "hjklk",
                    "cc1370ce67aa16c89721ee947e9733b2a3d2460db5b0ea6410288f426ad8d8040ea641",
                ),
                (
                    "bnmvc",
                    "d07e69664286712c3d268ca71464f2b3b2604346f833106f3e0f6a72276e57a16f3e0f",
                ),
            ];
            let mut values = HashMap::new();
            for &(ref key, ref hashed) in key_hashes.iter() {
                let new_root = merkle_db.set(&hashed, key.as_bytes()).unwrap();
                values.insert(hashed.to_string(), key.to_string());
                merkle_db.set_merkle_root(new_root).unwrap();
            }

            assert_ne!(init_root, merkle_db.get_merkle_root());
            let mut set_items = HashMap::new();
            // Perform some updates on the lower keys
            for &(_, ref key_hash) in key_hashes.iter() {
                set_items.insert(key_hash.clone().to_string(), "2.0".as_bytes().to_vec());
                values.insert(key_hash.clone().to_string(), "2.0".to_string());
            }

            // The first item below(e55420...89b9) shares a common prefix
            // with the first in set_items(e55420...620c)
            let delete_items = vec![
                "e55420c026596ee643e26fd93927249ea28fb5f359ddbd18bc02562dc7e8dbc93e89b9"
                    .to_string(),
                "cc1370ce67aa16c89721ee947e9733b2a3d2460db5b0ea6410288f426ad8d8040ea641"
                    .to_string(),
                "d07e69664286712c3d268ca71464f2b3b2604346f833106f3e0f6a72276e57a16f3e0f"
                    .to_string(),
            ];

            for hash in delete_items.iter() {
                values.remove(hash);
            }

            let virtual_root = merkle_db.update(&set_items, &delete_items, true).unwrap();

            // virtual root shouldn't match actual contents of tree
            assert!(merkle_db.set_merkle_root(virtual_root.clone()).is_err());

            let actual_root = merkle_db.update(&set_items, &delete_items, false).unwrap();
            // the virtual root should be the same as the actual root
            assert_eq!(virtual_root, actual_root);
            assert_ne!(actual_root, merkle_db.get_merkle_root());

            merkle_db.set_merkle_root(actual_root).unwrap();

            for (address, value) in values {
                assert_value_at_address(&merkle_db, &address, &value);
            }

            for address in delete_items {
                assert!(merkle_db.get(&address).is_err());
            }
        })
    }

    #[test]
    /// This test creates a merkle trie with multiple entries, and produces a
    /// second trie based on the first where an entry is change.
    ///
    /// - It verifies that both tries have a ChangeLogEntry
    /// - Prunes the parent trie
    /// - Verifies that the nodes written are gone
    /// - verifies that the parent trie's ChangeLogEntry is deleted
    fn merkle_trie_pruning_parent() {
        run_test(|merkle_path| {
            let db = make_lmdb(&merkle_path);
            let mut merkle_db = MerkleDatabase::new(db.clone(), None).expect("No db errors");
            let mut updates: HashMap<String, Vec<u8>> = HashMap::with_capacity(3);
            updates.insert("ab0000".to_string(), "0001".as_bytes().to_vec());
            updates.insert("ab0a01".to_string(), "0002".as_bytes().to_vec());
            updates.insert("abff00".to_string(), "0003".as_bytes().to_vec());

            let parent_root = merkle_db
                .update(&updates, &[], false)
                .expect("Update failed to work");
            merkle_db.set_merkle_root(parent_root.clone()).unwrap();

            let parent_root_bytes = ::hex::decode(parent_root.clone()).expect("Proper hex");
            // check that we have a change log entry for the new root
            let mut parent_change_log = expect_change_log(&db, &parent_root_bytes);
            assert!(parent_change_log.get_successors().is_empty());

            assert_value_at_address(&merkle_db, "ab0000", "0001");
            assert_value_at_address(&merkle_db, "ab0a01", "0002");
            assert_value_at_address(&merkle_db, "abff00", "0003");

            let successor_root = merkle_db
                .set("ab0000", "test".as_bytes())
                .expect("Set failed to work");
            let successor_root_bytes = ::hex::decode(successor_root.clone()).expect("proper hex");

            // Load the parent change log after the change.
            parent_change_log = expect_change_log(&db, &parent_root_bytes);
            let successor_change_log = expect_change_log(&db, &successor_root_bytes);

            assert_has_successors(&parent_change_log, &[&successor_root_bytes]);
            assert_eq!(parent_root_bytes, successor_change_log.get_parent());

            merkle_db
                .set_merkle_root(successor_root)
                .expect("Unable to apply the new merkle root");
            assert_eq!(
                parent_change_log
                    .get_successors()
                    .first()
                    .unwrap()
                    .get_deletions()
                    .len(),
                MerkleDatabase::prune(&db, &parent_root)
                    .expect("Prune should have no errors")
                    .len()
            );

            let reader = db.reader().unwrap();
            for addition in parent_change_log
                .get_successors()
                .first()
                .unwrap()
                .get_deletions()
            {
                assert!(reader.get(addition).is_none());
            }

            assert!(
                reader
                    .index_get(CHANGE_LOG_INDEX, &parent_root_bytes)
                    .expect("DB query should succeed")
                    .is_none()
            );

            assert!(merkle_db.set_merkle_root(parent_root).is_err());
        })
    }

    #[test]
    /// This test creates a merkle trie with multiple entries and produces two
    /// distinct successor tries from that first.
    ///
    /// - it verifies that all the tries have a ChangeLogEntry
    /// - it prunes one of the successors
    /// - it verifies the nodes from that successor are removed
    /// - it verifies that the pruned successor's ChangeLogEntry is removed
    /// - it verifies the original and the remaining successor still are
    ///   persisted
    fn merkle_trie_pruinng_successors() {
        run_test(|merkle_path| {
            let db = make_lmdb(&merkle_path);
            let mut merkle_db = MerkleDatabase::new(db.clone(), None).expect("No db errors");
            let mut updates: HashMap<String, Vec<u8>> = HashMap::with_capacity(3);
            updates.insert("ab0000".to_string(), "0001".as_bytes().to_vec());
            updates.insert("ab0a01".to_string(), "0002".as_bytes().to_vec());
            updates.insert("abff00".to_string(), "0003".as_bytes().to_vec());

            let parent_root = merkle_db
                .update(&updates, &[], false)
                .expect("Update failed to work");
            let parent_root_bytes = ::hex::decode(parent_root.clone()).expect("Proper hex");

            merkle_db.set_merkle_root(parent_root.clone()).unwrap();
            assert_value_at_address(&merkle_db, "ab0000", "0001");
            assert_value_at_address(&merkle_db, "ab0a01", "0002");
            assert_value_at_address(&merkle_db, "abff00", "0003");

            let successor_root_left = merkle_db
                .set("ab0000", "left".as_bytes())
                .expect("Set failed to work");
            let successor_root_left_bytes =
                ::hex::decode(successor_root_left.clone()).expect("proper hex");

            let successor_root_right = merkle_db
                .set("ab0a01", "right".as_bytes())
                .expect("Set failed to work");
            let successor_root_right_bytes =
                ::hex::decode(successor_root_right.clone()).expect("proper hex");

            let mut parent_change_log = expect_change_log(&db, &parent_root_bytes);
            let successor_left_change_log = expect_change_log(&db, &successor_root_left_bytes);
            expect_change_log(&db, &successor_root_right_bytes);

            assert_has_successors(
                &parent_change_log,
                &[&successor_root_left_bytes, &successor_root_right_bytes],
            );

            // Let's prune the left successor:

            assert_eq!(
                successor_left_change_log.get_additions().len(),
                MerkleDatabase::prune(&db, &successor_root_left)
                    .expect("Prune should have no errors")
                    .len()
            );

            parent_change_log = expect_change_log(&db, &parent_root_bytes);
            assert_has_successors(&parent_change_log, &[&successor_root_right_bytes]);

            assert!(merkle_db.set_merkle_root(successor_root_left).is_err());
        })
    }

    #[test]
    /// This test creates a merkle trie with multiple entries and produces a
    /// successor with duplicate That changes one new leaf, followed by a second
    /// successor that produces a leaf with the same hash.  When the pruning the
    /// initial root, the duplicate leaf node is not pruned as well.
    fn merkle_trie_pruning_duplicate_leaves() {
        run_test(|merkle_path| {
            let db = make_lmdb(&merkle_path);
            let mut merkle_db = MerkleDatabase::new(db.clone(), None).expect("No db errors");
            let updates: HashMap<String, Vec<u8>> = vec![
                ("ab0000".to_string(), "0001".as_bytes().to_vec()),
                ("ab0001".to_string(), "0002".as_bytes().to_vec()),
                ("ab0002".to_string(), "0003".as_bytes().to_vec()),
            ].into_iter()
            .collect();

            let parent_root = merkle_db
                .update(&updates, &[], false)
                .expect("Update failed to work");
            let parent_root_bytes = ::hex::decode(parent_root.clone()).expect("Proper hex");

            // create the middle root
            merkle_db.set_merkle_root(parent_root.clone()).unwrap();
            let updates: HashMap<String, Vec<u8>> = vec![
                ("ab0000".to_string(), "change0".as_bytes().to_vec()),
                ("ab0001".to_string(), "change1".as_bytes().to_vec()),
            ].into_iter()
            .collect();
            let successor_root_middle = merkle_db
                .update(&updates, &[], false)
                .expect("Update failed to work");

            // create the last root
            merkle_db
                .set_merkle_root(successor_root_middle.clone())
                .unwrap();
            // Set the value back to the original
            let successor_root_last = merkle_db
                .set("ab0000", "0001".as_bytes())
                .expect("Set failed to work");

            merkle_db.set_merkle_root(successor_root_last).unwrap();
            let parent_change_log = expect_change_log(&db, &parent_root_bytes);
            assert_eq!(
                parent_change_log
                    .get_successors()
                    .first()
                    .unwrap()
                    .get_deletions()
                    .len()
                    - 1,
                MerkleDatabase::prune(&db, &parent_root)
                    .expect("Prune should have no errors")
                    .len()
            );

            assert_value_at_address(&merkle_db, "ab0000", "0001");
        })
    }
    #[test]
    /// This test creates a merkle trie with multiple entries and produces a
    /// successor with duplicate That changes one new leaf, followed by a second
    /// successor that produces a leaf with the same hash.  When the pruning the
    /// last root, the duplicate leaf node is not pruned as well.
    fn merkle_trie_pruning_successor_duplicate_leaves() {
        run_test(|merkle_path| {
            let db = make_lmdb(&merkle_path);
            let mut merkle_db = MerkleDatabase::new(db.clone(), None).expect("No db errors");
            let updates: HashMap<String, Vec<u8>> = vec![
                ("ab0000".to_string(), "0001".as_bytes().to_vec()),
                ("ab0001".to_string(), "0002".as_bytes().to_vec()),
                ("ab0002".to_string(), "0003".as_bytes().to_vec()),
            ].into_iter()
            .collect();

            let parent_root = merkle_db
                .update(&updates, &[], false)
                .expect("Update failed to work");

            // create the middle root
            merkle_db.set_merkle_root(parent_root.clone()).unwrap();
            let updates: HashMap<String, Vec<u8>> = vec![
                ("ab0000".to_string(), "change0".as_bytes().to_vec()),
                ("ab0001".to_string(), "change1".as_bytes().to_vec()),
            ].into_iter()
            .collect();
            let successor_root_middle = merkle_db
                .update(&updates, &[], false)
                .expect("Update failed to work");

            // create the last root
            merkle_db
                .set_merkle_root(successor_root_middle.clone())
                .unwrap();
            // Set the value back to the original
            let successor_root_last = merkle_db
                .set("ab0000", "0001".as_bytes())
                .expect("Set failed to work");
            let successor_root_bytes =
                ::hex::decode(successor_root_last.clone()).expect("Proper hex");

            // set back to the parent root
            merkle_db.set_merkle_root(parent_root).unwrap();
            let last_change_log = expect_change_log(&db, &successor_root_bytes);
            assert_eq!(
                last_change_log.get_additions().len() - 1,
                MerkleDatabase::prune(&db, &successor_root_last)
                    .expect("Prune should have no errors")
                    .len()
            );

            assert_value_at_address(&merkle_db, "ab0000", "0001");
        })
    }

    fn expect_change_log(db: &LmdbDatabase, root_hash: &[u8]) -> ChangeLogEntry {
        let reader = db.reader().unwrap();
        protobuf::parse_from_bytes(
            &reader
                .index_get(CHANGE_LOG_INDEX, root_hash)
                .expect("No db errors")
                .expect("A change log entry"),
        ).expect("The change log entry to have bytes")
    }

    fn assert_has_successors(change_log: &ChangeLogEntry, successor_roots: &[&[u8]]) {
        assert_eq!(successor_roots.len(), change_log.get_successors().len());
        for successor_root in successor_roots {
            let mut has_root = false;
            for successor in change_log.get_successors() {
                if &successor.get_successor() == successor_root {
                    has_root = true;
                    break;
                }
            }
            if !has_root {
                panic!(format!(
                    "Root {} not found in change log {:?}",
                    ::hex::encode(successor_root),
                    change_log
                ));
            }
        }
    }

    #[test]
    fn leaf_iteration() {
        run_test(|merkle_path| {
            let mut merkle_db = make_db(merkle_path);

            {
                let mut leaf_iter = merkle_db.leaves(None).unwrap();
                assert!(
                    leaf_iter.next().is_none(),
                    "Empty tree should return no leaves"
                );
            }

            let addresses = vec!["ab0000", "aba001", "abff02"];
            for (i, key) in addresses.iter().enumerate() {
                let new_root = merkle_db
                    .set(key, format!("{:04x}", i * 10).as_bytes())
                    .unwrap();
                merkle_db.set_merkle_root(new_root).unwrap();
            }

            assert_value_at_address(&merkle_db, "ab0000", "0000");
            assert_value_at_address(&merkle_db, "aba001", "000a");
            assert_value_at_address(&merkle_db, "abff02", "0014");

            let mut leaf_iter = merkle_db.leaves(None).unwrap();

            assert_eq!(
                ("ab0000".into(), "0000".as_bytes().to_vec()),
                leaf_iter.next().unwrap().unwrap()
            );
            assert_eq!(
                ("aba001".into(), "000a".as_bytes().to_vec()),
                leaf_iter.next().unwrap().unwrap()
            );
            assert_eq!(
                ("abff02".into(), "0014".as_bytes().to_vec()),
                leaf_iter.next().unwrap().unwrap()
            );
            assert!(leaf_iter.next().is_none(), "Iterator should be Exhausted");

            // test that we can start from an prefix:
            let mut leaf_iter = merkle_db.leaves(Some("abff")).unwrap();
            assert_eq!(
                ("abff02".into(), "0014".as_bytes().to_vec()),
                leaf_iter.next().unwrap().unwrap()
            );
            assert!(leaf_iter.next().is_none(), "Iterator should be Exhausted");
        })
    }

    fn run_test<T>(test: T) -> ()
    where
        T: FnOnce(&str) -> () + panic::UnwindSafe,
    {
        let dbpath = temp_db_path();

        let testpath = dbpath.clone();
        let result = panic::catch_unwind(move || test(&testpath));

        remove_file(dbpath).unwrap();

        assert!(result.is_ok())
    }

    fn assert_value_at_address(merkle_db: &MerkleDatabase, address: &str, expected_value: &str) {
        let value = merkle_db.get(address);
        assert!(value.is_ok(), format!("Value not returned: {:?}", value));
        assert_eq!(Ok(expected_value), from_utf8(&value.unwrap().unwrap()));
    }

    fn make_lmdb(merkle_path: &str) -> LmdbDatabase {
        let ctx = LmdbContext::new(
            Path::new(merkle_path),
            INDEXES.len(),
            Some(120 * 1024 * 1024),
        ).map_err(|err| DatabaseError::InitError(format!("{}", err)))
        .unwrap();
        LmdbDatabase::new(ctx, &INDEXES)
            .map_err(|err| DatabaseError::InitError(format!("{}", err)))
            .unwrap()
    }

    fn make_db(merkle_path: &str) -> MerkleDatabase {
        MerkleDatabase::new(make_lmdb(merkle_path), None).unwrap()
    }

    fn temp_db_path() -> String {
        let mut temp_dir = env::temp_dir();

        let thread_id = thread::current().id();
        temp_dir.push(format!("merkle-{:?}.lmdb", thread_id));
        temp_dir.to_str().unwrap().to_string()
    }

    fn hex_hash(b: &[u8]) -> String {
        ::hex::encode(hash(b))
    }

}
