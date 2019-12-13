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

use batch::Batch;
use state::settings_view::SettingsView;
use transaction::Transaction;

/// Retrieve the validation rules stored in state and check that the
/// given batches do not violate any of those rules. These rules include:
///
///     NofX: Only N of transaction type X may be included in a block.
///     XatY: A transaction of type X must be in the list at position Y.
///     local: A transaction must be signed by the given public key
///
/// If any setting stored in state does not match the required format for
/// that rule, the rule will be ignored.
///
/// Args:
///     settings_view (:obj:SettingsView): the settings view to find the
///         current rule values
///     expected_signer (str): the public key used to use for local signing
///     batches (:list:Batch): the list of batches to validate
pub fn enforce_validation_rules(
    settings_view: &SettingsView,
    expected_signer: &str,
    batches: &[&Batch],
) -> bool {
    let rules = settings_view
        .get_setting_str("sawtooth.validator.block_validation_rules", None)
        .expect("Unable to get setting");
    enforce_rules(rules, expected_signer, batches)
}

fn enforce_rules(rules: Option<String>, expected_signer: &str, batches: &[&Batch]) -> bool {
    if rules.is_none() {
        return true;
    }

    let mut transactions = vec![];
    batches
        .iter()
        .for_each(|batch| transactions.extend(&batch.transactions));

    let mut valid = true;
    for rule_str in rules.unwrap().split(';') {
        if let Some((rule_type, arguments)) = parse_rule(rule_str) {
            if rule_type == "NofX" {
                valid = do_nofx(&transactions, &arguments);
            } else if rule_type == "XatY" {
                valid = do_xaty(&transactions, &arguments);
            } else if rule_type == "local" {
                valid = do_local(&transactions, expected_signer, &arguments);
            }

            if !valid {
                return false;
            }
        } else {
            warn!(
                "Validation rule Ignored, not in the correct format: {}",
                rule_str
            );
        }
    }

    valid
}

/// Only N of transaction type X may be included in a block. The first
/// argument must be interpretable as an integer. The second argument is
/// interpreted as the name of a transaction family. For example, the
/// string "NofX:2,intkey" means only allow 2 intkey transactions per
/// block.
fn do_nofx(transactions: &[&Transaction], arguments: &[&str]) -> bool {
    let (limit, family) = if arguments.len() == 2 {
        let limit: usize = match arguments[0].trim().parse() {
            Ok(i) => i,
            Err(_) => {
                warn!(
                    "Ignore, NofX requires limit to be a number, not {}",
                    arguments[0]
                );
                return true;
            }
        };
        let family = arguments[1].trim();
        (limit, family)
    } else {
        warn!(
            "Ignore, NofX requires arguments in the format 'limit,family' not {:?}",
            arguments
        );
        return true;
    };

    let mut count = 0usize;

    for txn in transactions {
        if txn.family_name == family {
            count += 1;
        }

        if count > limit {
            debug!("Too many transactions of type {}", family);
            return false;
        }
    }

    true
}

/// A transaction of type X must be in the block at position Y. The
/// first argument is interpreted as the name of a transaction family.
/// The second argument must be interpretable as an integer and defines
/// the index of the transaction in the block that must be checked.
/// Negative numbers can be used and count backwards from the last
/// transaction in the block. The first transaction in the block has
/// index 0. The last transaction in the block has index -1. If abs(Y)
/// is larger than the number of transactions per block, then there
/// would not be a transaction of type X at Y and the block would be
/// invalid. For example, the string "XatY:intkey,0" means the first
/// transaction in the block must be an intkey transaction.
fn do_xaty(transactions: &[&Transaction], arguments: &[&str]) -> bool {
    let (family, position) = if arguments.len() == 2 {
        let family = arguments[0].trim();
        let position: usize = match arguments[1].trim().parse() {
            Ok(i) => i,
            Err(_) => {
                warn!(
                    "Ignore, XatY requires position to be a number, not {}",
                    arguments[1]
                );
                return true;
            }
        };
        (family, position)
    } else {
        warn!(
            "Ignore, XatY requires arguments in the format 'family,position' not {:?}",
            arguments
        );
        return true;
    };

    if position >= transactions.len() {
        debug!(
            "Block does not have enough transactions to valid this rule XatY:{:?}",
            arguments
        );
        return false;
    }

    let txn = transactions[position];
    if txn.family_name != family {
        debug!(
            "Transaction at position {} is not of type {}",
            position, family
        );
        return false;
    }

    true
}

/// A transaction must be signed by the same key as the block. This
/// rule takes a list of transaction indices in the block and enforces the
/// rule on each. This rule is useful in combination with the other rules
/// to ensure a client is not submitting transactions that should only be
/// injected by the winning validator.
fn do_local(transactions: &[&Transaction], expected_signer: &str, arguments: &[&str]) -> bool {
    let indices: Result<Vec<usize>, _> = arguments.iter().map(|s| s.trim().parse()).collect();

    if indices.is_err() || indices.as_ref().unwrap().is_empty() {
        warn!(
            "Ignore, local requires one or more comma separated integers \
             that represent indices, not {:?}",
            arguments
        );
        return true;
    }

    for index in indices.unwrap() {
        if index >= transactions.len() {
            debug!(
                "Ignore, Block does not have enough transactions to validate this rule local: {}",
                index
            );
            continue;
        }

        if transactions[index].signer_public_key != expected_signer {
            debug!(
                "Transaction at  position {} was not signed by the expected signer.",
                index
            );
            return false;
        }
    }

    true
}

/// Splits up a rule string in the form of "<rule_type>:<rule_arg>,*"
fn parse_rule(rule: &str) -> Option<(&str, Vec<&str>)> {
    let mut rule_parts: Vec<&str> = rule.split(':').collect();
    if rule_parts.len() != 2 {
        return None;
    }

    let rule_args = rule_parts.pop().unwrap().split(',').collect::<Vec<_>>();
    let rule_type = rule_parts.pop().unwrap();

    Some((rule_type.trim(), rule_args))
}

#[cfg(test)]
mod tests {
    use super::*;
    use batch::Batch;
    use transaction::Transaction;

    /// Test that if no validation rules are set, the block is valid.
    #[test]
    fn test_no_setting() {
        let batches = make_batches(&["intkey"], "pub_key");
        assert!(enforce_rules(
            None,
            "pub_key",
            &batches.iter().collect::<Vec<_>>()
        ));
    }

    /// Test that if NofX Rule is set, the validation rule is checked
    /// correctly. Test:
    ///     1. Valid Block, has one or less intkey transactions.
    ///     2. Invalid Block, to many intkey transactions.
    ///     3. Valid Block, ignore rule because it is formatted incorrectly.
    #[test]
    fn test_n_of_x() {
        let batches = make_batches(&["intkey"], "pub_key");
        assert!(enforce_rules(
            Some("NofX:1,intkey".to_string()),
            "pub_key",
            &batches.iter().collect::<Vec<_>>()
        ));
        assert!(!enforce_rules(
            Some("NofX:0,intkey".to_string()),
            "pub_key",
            &batches.iter().collect::<Vec<_>>()
        ));
        assert!(enforce_rules(
            Some("NofX:0".to_string()),
            "pub_key",
            &batches.iter().collect::<Vec<_>>()
        ));
    }

    /// Test that if XatY Rule is set, the validation rule is checked
    /// correctly. Test:
    ///     1. Valid Block, has intkey at the 0th position.
    ///     2. Invalid Block, does not have an blockinfo txn at the 0th postion
    ///     3. Valid Block, ignore rule because it is formatted incorrectly.
    #[test]
    fn test_x_at_y() {
        let batches = make_batches(&["intkey"], "pub_key");
        assert!(enforce_rules(
            Some("XatY:intkey,0".to_string()),
            "pub_key",
            &batches.iter().collect::<Vec<_>>()
        ));
        assert!(!enforce_rules(
            Some("XatY:blockinfo,0".to_string()),
            "pub_key",
            &batches.iter().collect::<Vec<_>>()
        ));
        assert!(enforce_rules(
            Some("XatY:0".to_string()),
            "pub_key",
            &batches.iter().collect::<Vec<_>>()
        ));
    }

    /// Test that if local Rule is set, the validation rule is checked
    /// correctly. Test:
    ///     1. Valid Block, first transaction is signed by the expected signer.
    ///     2. Invalid Block, first transaction is not signed by the expected
    ///        signer.
    ///     3. Valid Block, ignore rule because it is formatted incorrectly.
    #[test]
    fn test_local() {
        let batches = make_batches(&["intkey"], "pub_key");
        assert!(enforce_rules(
            Some("local:0".to_string()),
            "pub_key",
            &batches.iter().collect::<Vec<_>>()
        ));
        assert!(!enforce_rules(
            Some("local:0".to_string()),
            "another_pub_key",
            &batches.iter().collect::<Vec<_>>()
        ));
        assert!(enforce_rules(
            Some("local".to_string()),
            "pub_key",
            &batches.iter().collect::<Vec<_>>()
        ));
    }

    /// Test that if multiple rules are set, they are all checked correctly.
    /// Block should be valid.
    #[test]
    fn test_all_at_once() {
        let batches = make_batches(&["intkey"], "pub_key");
        assert!(enforce_rules(
            Some("NofX:1,intkey;XatY:intkey,0;local:0".to_string()),
            "pub_key",
            &batches.iter().collect::<Vec<_>>()
        ));
    }

    /// Test that if multiple rules are set, they are all checked correctly.
    /// Block is invalid, because there are too many intkey transactions
    #[test]
    fn test_all_at_once_bad_number_of_intkey() {
        let batches = make_batches(&["intkey"], "pub_key");
        assert!(!enforce_rules(
            Some("NofX:0,intkey;XatY:intkey,0;local:0".to_string()),
            "pub_key",
            &batches.iter().collect::<Vec<_>>()
        ));
    }

    /// Test that if multiple rules are set, they are all checked correctly.
    /// Block is invalid, there is not a blockinfo transactions at the 0th
    /// position.
    #[test]
    fn test_all_at_once_bad_family_at_index() {
        let batches = make_batches(&["intkey"], "pub_key");
        assert!(!enforce_rules(
            Some("NofX:1,intkey;XatY:blockinfo,0;local:0".to_string()),
            "pub_key",
            &batches.iter().collect::<Vec<_>>()
        ));
    }

    /// Test that if multiple rules are set, they are all checked correctly.
    /// Expected signer is invalid, transaction at the 0th position is not
    /// signed by the expected signer.
    #[test]
    fn test_all_at_once_signer_key() {
        let batches = make_batches(&["intkey"], "pub_key");
        assert!(!enforce_rules(
            Some("NofX:1,intkey;XatY:intkey,0;local:0".to_string()),
            "not_same_pubkey",
            &batches.iter().collect::<Vec<_>>()
        ));
    }

    fn make_batches(families: &[&str], pubkey: &str) -> Vec<Batch> {
        let transactions: Vec<Transaction> = families
            .iter()
            .enumerate()
            .map(|(i, family)| Transaction {
                family_name: family.to_string(),
                family_version: "0.test".into(),
                signer_public_key: pubkey.to_string(),
                batcher_public_key: pubkey.to_string(),
                inputs: vec![],
                outputs: vec![],
                dependencies: vec![],
                payload: vec![],
                payload_sha512: String::new(),
                header_signature: format!("{}_{}", family, i),
                nonce: String::new(),

                header_bytes: vec![],
            })
            .collect();

        vec![Batch {
            transaction_ids: transactions
                .iter()
                .map(|t| t.header_signature.clone())
                .collect(),
            transactions: transactions,
            signer_public_key: pubkey.to_string(),
            trace: false,
            header_bytes: vec![],
            header_signature: "test_batch".into(),
        }]
    }
}
