# Copyright 2017 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import logging

from sawtooth_validator.protobuf.transaction_pb2 import TransactionHeader

LOGGER = logging.getLogger(__name__)


def enforce_validation_rules(settings_view, expected_signer, batches):
    """
    Retrieve the validation rules stored in state and check that the
    given batches do not violate any of those rules. These rules include:

        NofX: Only N of transaction type X may be included in a block.
        XatY: A transaction of type X must be in the list at position Y.
        local: A transaction must be signed by the given public key

    If any setting stored in state does not match the required format for
    that rule, the rule will be ignored.

    Args:
        settings_view (:obj:SettingsView): the settings view to find the
            current rule values
        expected_signer (str): the public key used to use for local signing
        batches (:list:Batch): the list of batches to validate

    """
    rules = settings_view.get_setting(
        "sawtooth.validator.block_validation_rules")

    if rules is None:
        return True

    transactions = []
    for batch in batches:
        transactions += batch.transactions

    rules = rules.split(";")
    valid = True
    for rule in rules:
        try:
            rule_type, arguments = rule.split(":")
        except ValueError:
            LOGGER.warning("Validation Rule Ignored, not in the correct "
                           "format: %s",
                           rule)
            continue

        rule_type = rule_type.strip()
        # NofX: Only N of transaction type X may be included in a block.
        if rule_type == "NofX":
            valid = _do_nofx(transactions, arguments)

        # XatY: A transaction of type X must be in the block at position Y.
        elif rule_type == "XatY":
            valid = _do_xaty(transactions, arguments)

        # local: A transaction must be signed by the same key as the block.
        elif rule_type == "local":
            valid = _do_local(
                transactions, expected_signer, arguments)

        if not valid:
            return False

    return valid


def _do_nofx(transactions, arguments):
    """
    Only N of transaction type X may be included in a block. The first
    argument must be interpretable as an integer. The second argument is
    interpreted as the name of a transaction family. For example, the
    string "NofX:2,intkey" means only allow 2 intkey transactions per
    block.
    """
    try:
        num, family = arguments.split(',')
        limit = int(num.strip())
    except ValueError:
        LOGGER.warning("Ignore, NofX requires arguments in the format "
                       "int,family not %s", arguments)
        return True
    count = 0
    family = family.strip()
    for txn in transactions:
        header = TransactionHeader()
        header.ParseFromString(txn.header)
        if header.family_name == family:
            count += 1

        if count > limit:
            LOGGER.debug("Too many transactions of type %s", family)
            return False

    return True


def _do_xaty(transactions, arguments):
    """
    A transaction of type X must be in the block at position Y. The
    first argument is interpreted as the name of a transaction family.
    The second argument must be interpretable as an integer and defines
    the index of the transaction in the block that must be checked.
    Negative numbers can be used and count backwards from the last
    transaction in the block. The first transaction in the block has
    index 0. The last transaction in the block has index -1. If abs(Y)
    is larger than the number of transactions per block, then there
    would not be a transaction of type X at Y and the block would be
    invalid. For example, the string "XatY:intkey,0" means the first
    transaction in the block must be an intkey transaction.
    """
    try:
        family, num = arguments.split(',')
        position = int(num.strip())
    except ValueError:
        LOGGER.warning("Ignore, XatY requires arguments in the format "
                       "family,position not %s", arguments)
        return True

    family = family.strip()
    if abs(position) >= len(transactions):
        LOGGER.debug("Block does not have enough transactions to "
                     "validate this rule XatY:%s", arguments)
        return False
    txn = transactions[position]

    header = TransactionHeader()
    header.ParseFromString(txn.header)
    if header.family_name != family:
        LOGGER.debug("Transaction at postion %s is not of type %s",
                     position, family)
        return False
    return True


def _do_local(transactions, expected_signer, arguments):
    """
    A transaction must be signed by the same key as the block. This
    rule takes a list of transaction indices in the block and enforces the
    rule on each. This rule is useful in combination with the other rules
    to ensure a client is not submitting transactions that should only be
    injected by the winning validator.
    """
    indices = arguments.split(",")
    txns_len = len(transactions)
    for index in indices:
        try:
            index = int(index.strip())
        except ValueError:
            LOGGER.warning("Ignore, local requries one or more comma "
                           "seperated integers that represent indices, not"
                           " %s", arguments)
            return True

        if abs(index) >= txns_len:
            LOGGER.debug("Ignore, Block does not have enough "
                         "transactions to validate this rule local:%s",
                         index)
            continue
        txn = transactions[index]
        header = TransactionHeader()
        header.ParseFromString(txn.header)

        if header.signer_public_key != expected_signer:
            LOGGER.debug("Transaction at postion %s was not signed by the"
                         " same key as the block.", index)
            return False
    return True
