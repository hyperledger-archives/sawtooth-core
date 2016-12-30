# Copyright 2016 Intel Corporation
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
# ------------------------------------------------------------------------------

from __future__ import print_function

import time
from operator import itemgetter

from sawtooth.cli.stats_lib.stats_utils import ValidatorCommunications
from sawtooth.cli.stats_lib.stats_utils import get_public_attrs_as_dict

from sawtooth.cli.stats_lib.stats_utils import StatsModule

# Reference value in gossip.common - NullIdentifier
# Not imported here to avoid needless ECDSARecoveryModule dependency
# GENESIS_PREVIOUS_BLOCK_ID = NullIdentifier
GENESIS_PREVIOUS_BLOCK_ID = "0000000000000000"


class BlockClient(object):
    def __init__(self, bc_id, full_url,
                 look_back_count=5, validator=None):
        self.validator = validator
        self.bc_id = bc_id
        self.url = full_url
        self.name = "block_client_{0}".format(bc_id)

        self.responding = False
        self.bc_state = "WAITING"
        self.bc_response_status = " - First Contact"

        self.validator_comm = ValidatorCommunications()

        self.new_blocks = []
        self.last_block_id = GENESIS_PREVIOUS_BLOCK_ID
        self.last_block_num = -1
        self.last_block_previous_block_id = None
        self.lb_count = look_back_count
        self.current_branch = None

        self.path = None

    def blocks_request(self):
        # request block info for 5 newest blocks from specified validator url
        if self.validator_comm is not None:
            self.path = self.url + "/block?info=1&blockcount=5"
            self.validator_comm.get_request(
                self.path,
                self._blocks_completion,
                self._blocks_error)

    def _blocks_completion(self, block_response, response_code):
        self.bc_state = "RESP_{}".format(response_code)
        if response_code is 200:
            self.responding = True
            self.bc_response_status = "Response code = 200"
            self.update(block_response)
        else:
            self.responding = False
            self.bc_response_status = "Response code not 200"

    def _blocks_error(self, failure):
        self.responding = False
        self.bc_state = "NO_RESP"
        self.bc_response_status = failure.type.__name__
        return

    def update(self, block_response):
        block_id = block_response["head"]
        blocks = block_response["blocks"]
        block = blocks.get(block_id)
        # return if same block id and number as last time,
        # no new blocks available
        if block["BlockNum"] == self.last_block_num and \
                block_id == self.last_block_id:
            return
        newest_block_id = block_id
        newest_block_num = block["BlockNum"]
        while True:
            block = blocks.get(block_id, None)
            # break if end of block sequence
            if block is None:
                break
            block["Identifier"] = block_id
            self.new_blocks.append(block)
            # break if block immediately follows last block;
            # no further blocks required
            if block["BlockNum"] == self.last_block_num + 1 and \
                    block["PreviousBlockID"] == self.last_block_id:
                break
            block_id = block["PreviousBlockID"]
        self.last_block_id = newest_block_id
        self.last_block_num = newest_block_num

    def get_new_blocks(self):
        new_blocks = list(self.new_blocks)
        self.new_blocks = []
        return new_blocks


class BlockChainBranch(object):
    def __init__(self):
        self.bcb_id = None

        # local attributes
        self.blocks = {}
        self._predecessor_ids = {}
        self._block_numbers = {}

        self._is_active_list = []
        self.is_active_history = []

        self.head_block_id = None
        self.tail_block_id = None

        self.head_block_num = None
        self.tail_block_num = None

        self.is_active = False

        self.create_time = time.time()
        self.last_active_time = time.time()

        # these variable are used by find_ancestors() in BranchManager()
        # and are not modified by BlockChainBranch
        self.ancestor_branch = None
        self.ancestor_branch_id = None
        self.ancestor_block_id = None
        self.ancestor_block_num = None
        self.ancestor_found = None

    @property
    def block_count(self):
        return len(self.blocks)

    @property
    def is_active_count(self):
        return len(self._is_active_list)

    def assess(self, block):
        """
        adds block to branch if branch is empty, else....
        adds block to branch if block is a direct predecessor or successor
        returns true if block is added or exact copy already exists in branch
        otherwise returns false
        """
        current_block_num = block["BlockNum"]
        current_block_id = block["Identifier"]
        current_block_pbid = block["PreviousBlockID"]
        if len(self._block_numbers) is 0:
            self._add_block(block)
            self.head_block_id = current_block_id
            self.tail_block_id = current_block_id
            self.head_block_num = current_block_num
            self.tail_block_num = current_block_num
            # first block in branch
            return True
        # if id in blocks{} and block matches
        existing_block = self.blocks.get(current_block_id, None)
        if existing_block is not None:
            # return true if current block id exists in blocks{}
            # and blocks match (have same block num and predecessor id)
            return existing_block["BlockNum"] == current_block_num and \
                existing_block["PreviousBlockID"] == current_block_pbid
        # current block id does not exist in blocks{} - continue
        existing_block_num = self._block_numbers.get(current_block_num, None)
        if existing_block_num is not None:
            # block number exists in block_numbers{} and cannot be replaced
            return False
        # current block number does not exist in block_numbers{} - continue
        # check if current block is an immediate predecessor...
        # current blocks previous block id must be in predecessor_ids{}
        # and successor block number must equal current block number + 1
        successor_block_id = self._predecessor_ids.get(current_block_id, None)
        if successor_block_id is not None:
            successor_block = self.blocks[successor_block_id]
            if successor_block["PreviousBlockID"] == current_block_id and \
                    successor_block["BlockNum"] == current_block_num + 1:
                self._add_block(block)
                self.tail_block_id = current_block_id
                self.tail_block_num = current_block_num
                # block is immediate predecessor
                return True
        # else check if current block is an immediate successor...
        # current blocks previous block id must exist in blocks
        # and predecessor block number must equal current block number - 1
        predecessor_block = self.blocks.get(current_block_pbid, None)
        if predecessor_block is not None:
            if predecessor_block["BlockNum"] == current_block_num - 1:
                self._add_block(block)
                self.head_block_id = current_block_id
                self.head_block_num = current_block_num
                # block is immediate successor
                return True
        # block was neither added to nor found in branch
        return False

    def _add_block(self, current_block):
        current_block_num = current_block["BlockNum"]
        current_block_id = current_block["Identifier"]
        current_block_pbid = current_block["PreviousBlockID"]
        self.blocks[current_block_id] = current_block
        self._predecessor_ids[current_block_pbid] = current_block_id
        self._block_numbers[current_block_num] = current_block_id

    def remove_head(self):
        if self.head_block_id == self.tail_block_id:
            self._remove_last()
        else:
            head_block = self.blocks.get(self.head_block_id)
            predecessor_block_id = head_block["PreviousBlockID"]
            predecessor_block = self.blocks.get(predecessor_block_id)
            self._remove_block(self.head_block_id)
            self.head_block_id = predecessor_block_id
            self.head_block_num = predecessor_block["BlockNum"]

    def remove_tail(self):
        if self.head_block_id == self.tail_block_id:
            self._remove_last()
        else:
            successor_block_id = self._predecessor_ids[self.tail_block_id]
            successor_block = self.blocks.get(successor_block_id)
            self._remove_block(self.tail_block_id)
            self.tail_block_id = successor_block_id
            self.tail_block_num = successor_block["BlockNum"]

    def _remove_last(self):
        self._remove_block(self.head_block_id)
        self.head_block_id = None
        self.tail_block_id = None
        self.head_block_num = None
        self.tail_block_num = None

    def _remove_block(self, block_id):
        removed_block = self.blocks.pop(block_id)
        self._predecessor_ids.pop(removed_block["PreviousBlockID"])
        self._block_numbers.pop(removed_block["BlockNum"])

    def print_branch(self, do_print=False, print_all=False, print_terse=False):
        block_list = []
        info_list = []
        for _, block in self.blocks.iteritems():
            block_list.append([block["Identifier"], block["BlockNum"],
                               block["PreviousBlockID"]])
        sorted_list = sorted(block_list, key=itemgetter(1))
        if print_terse:
            for block_id, block_num, pred_id in sorted_list:
                info_list.append(
                    [{"Identifier": block_id, "BlockNum": block_num}])
                if do_print:
                    print(block_id, end=' ')
            print()
        else:
            for block_id, block_num, pred_id in sorted_list:
                block = self.blocks[block_id]
                block_info = {"Identifier": block_id,
                              "BlockNum": block_num,
                              "PreviousBlockID": pred_id}
                if do_print:
                    print(block["Identifier"], block["BlockNum"], block[
                        "PreviousBlockID"], end=' ')
                if print_all:
                    successor = self._predecessor_ids.get(
                        block["PreviousBlockID"], None)
                    bid = self._block_numbers.get(block["BlockNum"], None)
                    block_info["PreviousIDToSuccessorID"] = successor
                    block_info["BlockNumToBlockID"] = bid
                    if do_print:
                        print(successor, bid, end=' ')
                if do_print:
                    print()
                info_list.append(block_info)
        return info_list

    def get_stats_as_dict(self):
        stats = {}
        stats['head_block_id'] = self.head_block_id
        stats['tail_block_id'] = self.tail_block_id
        stats['head_block_num'] = self.head_block_num
        stats['tail_block_num'] = self.tail_block_num
        stats['is_active'] = self.is_active
        stats['create_time'] = self.create_time
        stats['last_active_time'] = self.last_active_time
        stats['ancestor_branch_id'] = self.ancestor_branch_id
        stats['ancestor_block_id'] = self.ancestor_block_id
        stats['ancestor_block_num'] = self.ancestor_block_num
        stats['ancestor_found'] = self.ancestor_found
        stats['block_count'] = self.block_count
        stats['is_active_count'] = self.is_active_count
        return stats


class BlockChainFork(object):
    def __init__(self):
        # private attributes
        self.branches = []
        self._head_branch = None
        self._tail_branch = None
        # used by find_fork_intercept() in branch_manager
        self.intercept_branch = None

        # public attributes - will be published as stats
        self.bcf_id = ""

        self.validator_count = 0

        self.head_block_id = None
        self.head_block_num = None
        self.tail_block_id = None
        self.tail_block_num = None

        self.block_count = 0

        # used by find_fork_intercept() in branch_manager
        self.intercept_branch_id = None
        self.intercept_block_id = None
        self.intercept_block_num = None
        self.intercept_where = None
        self.fork_intercept_length = None

        self.is_parent = False
        self.parent_fork_id = None

    @property
    def branch_count(self):
        return len(self.branches)

    def build_fork(self, active_branch):
        self._head_branch = active_branch
        self.head_block_id = self._head_branch.head_block_id
        self.head_block_num = self._head_branch.head_block_num
        self.validator_count = self._head_branch.is_active_count

        fork_branches = []
        block_count = 0
        branch = self._head_branch
        ancestor_branch_intercept = branch.head_block_num

        while True:
            assert branch, "fork: branch object does not exist"
            assert isinstance(branch, BlockChainBranch), "fork: wrong type"
            fork_branches.append(branch)
            block_count += (ancestor_branch_intercept -
                            branch.tail_block_num) + 1
            ancestor_branch_intercept = branch.ancestor_block_num
            self._tail_branch = branch
            self.tail_block_id = branch.tail_block_id
            self.tail_block_num = branch.tail_block_num
            # get the next branch
            branch = branch.ancestor_branch
            if branch is None:
                break

        if self.head_block_num is not None:
            # assert that number of blocks in fork equal to
            # head block num - tail block num (0-based index)
            assert self.head_block_num - self.tail_block_num == block_count - 1
        self.branches = fork_branches
        self.block_count = block_count

    def get_successor_info(self, info_branch):
        index = self.branches.index(info_branch)
        if index is 0:
            # the head branch doesn't have a successor to get
            # ancestor block id and num from, so....
            return self.branches[0].head_block_id, self.branches[
                0].head_block_num
        else:
            return self.branches[index - 1].ancestor_block_id, self.branches[
                index - 1].ancestor_block_num

    def find_intercept(self, child_fork):
        '''
        while stepping through child fork branches from head to tail
        if the child fork branch is found in parent fork branches
        if the child fork branch intercept block num is less than
        the parent fork branch intercept block num
        then intercept block num is child intercept block num
        if the child fork branch intercept block num is greater than
        the parent fork branch intercept block num
        then intercept block num is parent intercept block num
        else there is no intercept
        '''

        for child_fork_branch in child_fork.branches:
            if child_fork_branch in self.branches:
                parent_intercept_block_id, parent_intercept_block_num = \
                    self.get_successor_info(child_fork_branch)
                child_intercept_block_id, child_intercept_block_num = \
                    child_fork.get_successor_info(child_fork_branch)
                if child_intercept_block_num < parent_intercept_block_num:
                    child_fork.intercept_block_id = child_intercept_block_id
                    child_fork.intercept_block_num = child_intercept_block_num
                    child_fork.intercept_where = "less than"
                elif child_intercept_block_num >= parent_intercept_block_num:
                    child_fork.intercept_block_id = parent_intercept_block_id
                    child_fork.intercept_block_num = parent_intercept_block_num
                    if child_intercept_block_num == parent_intercept_block_num:
                        child_fork.intercept_where = "equal"
                    else:
                        child_fork.intercept_where = "greater than"
                else:
                    child_fork.intercept_where = "error"
                    assert False, "should never get here"

                child_fork.intercept_branch = child_fork_branch
                child_fork.intercept_branch_id = child_fork_branch.bcb_id
                child_fork.fork_intercept_length = \
                    child_fork.head_block_num - child_fork.intercept_block_num
                return True

        child_fork.intercept_where = "none"
        return False

    def get_stats_as_dict(self):
        stats = {}
        stats['validator_count'] = self.validator_count
        stats['head_block_id'] = self.head_block_id
        stats['head_block_num'] = self.head_block_num
        stats['tail_block_id'] = self.tail_block_id
        stats['tail_block_num'] = self.tail_block_num
        stats['block_count'] = self.block_count
        stats['intercept_branch_id'] = self.intercept_branch_id
        stats['intercept_block_id'] = self.intercept_block_id
        stats['intercept_block_num'] = self.intercept_block_num
        stats['intercept_where'] = self.intercept_where
        stats['fork_intercept_length'] = self.fork_intercept_length
        stats['is_parent'] = self.is_parent
        stats['parent_fork_id'] = self.parent_fork_id
        stats['branch_count'] = self.branch_count
        return stats


class ForkManagerStats(object):
    def __init__(self):
        self.status = None
        self.fork_count = 0
        self.parent_count = 0
        self.child_count = 0
        self.longest_child_fork_length = 0
        self.validator_count = 0

    def print_stats(self):
        print("network fork status:", self.status, end=' ')
        print("  fork count:", self.fork_count, end=' ')
        print("  parent forks:", self.parent_count, end=' ')
        print("  child forks:", self.child_count, end=' ')
        print("  longest child fork:", self.longest_child_fork_length)

    def get_stats_as_dict(self):
        return get_public_attrs_as_dict(self)


class BranchManagerStats(object):
    def __init__(self):
        self.validators = 0
        self.blocks_processed = 0
        self.identified = 0
        self.active = 0
        self.longest = 0
        self.longest_active = 0
        self.next_longest_active = 0

        self.branch_count = 0
        self.non_zero_branch_count = 0
        self.active_branch_count = 0
        self.one_block_branch_count = 0
        self.sorted_longest_active = 0

    def print_stats(self):
        print("branches identified:", self.identified, end=' ')
        print("  active branches:", self.active, end=' ')
        print("  longest branch length:", self.longest, end=' ')
        print("  longest active branch length:", self.longest_active, end=' ')
        print("  next longest active branch length:",
              self.next_longest_active, end=' ')
        print("  validator count:", self.validators)

    def get_stats_as_dict(self):
        return get_public_attrs_as_dict(self)


class BranchManager(StatsModule):
    def __init__(self, endpoint_manager, config):

        super(BranchManager, self).__init__()
        self.branches = []

        self.epm = endpoint_manager
        self.known_endpoint_names = []
        self.block_clients = []

        self.bm_stats = BranchManagerStats()
        self.f_stats = ForkManagerStats()

        self.forks = []
        self.sorted_longest_active = None

    @property
    def branch_count(self):
        return len(self.branches)

    @property
    def fork_count(self):
        return len(self.forks)

    def connect(self):
        self.update_client_list()

    def collect(self):
        self.update()

    def update_client_list(self):
        # add validator stats client for each endpoint name
        endpoints = self.epm.endpoints
        for val_num, endpoint in enumerate(endpoints.values()):
            if endpoint["Name"] not in self.known_endpoint_names:
                val_num = len(self.known_endpoint_names)
                url = 'http://{0}:{1}'.format(
                    endpoint["Host"], endpoint["HttpPort"])
                bc = BlockClient(val_num, url)
                bc.name = endpoint["Name"]
                self.block_clients.append(bc)
                self.known_endpoint_names.append(endpoint["Name"])
        self.bm_stats.validators = len(self.block_clients)

    def update(self):
        self._update_branches()
        self._merge_branches()
        self._find_ancestors()
        self._identify_active_branches()
        self._find_forks()
        self._find_fork_intercepts()
        self._update_stats()

    def _update_branches(self):
        """
        given a list of BlockClients, for each BlockClient,
        get accumulated blocks and update branches
        """
        for bc in self.block_clients:
            blocks = bc.get_new_blocks()
            self.bm_stats.blocks_processed += len(blocks)
            for block in blocks:
                self.branch_update(block)

        for bc in self.block_clients:
            bc.blocks_request()

    def branch_update(self, block):
        """
        for each branch in branches....
        assess whether the current block should be added to the branch
        if the block is not found in any branches, create a new one and add it
        """
        found = False
        for branch in self.branches:
            if branch.assess(block):
                found = True

        if not found:
            bc_branch = BlockChainBranch()
            bc_branch.bcb_id = "brn_{0:08d}".format(self.branch_count)
            bc_branch.assess(block)
            self.branches.append(bc_branch)

    def _merge_branches(self):
        """
        make a list of branches sorted by block count
        merge the largest branch with each smaller branch
        """
        branches = []
        for branch in self.branches:
            branches.append([branch, branch.block_count])
        sorted_branches = sorted(branches, key=itemgetter(1), reverse=True)
        for i in range(0, len(sorted_branches) - 1):
            destination_branch = sorted_branches[i][0]
            for j in range(i + 1, len(sorted_branches)):
                source_branch = sorted_branches[j][0]
                self._branch_merge(source_branch, destination_branch)

    @staticmethod
    def _branch_merge(source_branch, destination_branch):
        """
        move leading and tailing blocks from source branch
        to destination branch, effectively eliminating duplicate blocks
        """
        sb = source_branch
        db = destination_branch
        blocks_merged = 0

        while sb.tail_block_id is not None and db.assess(
                sb.blocks.get(sb.tail_block_id)):
            sb.remove_tail()
            blocks_merged += 1

        while sb.head_block_id is not None and db.assess(
                sb.blocks.get(sb.head_block_id)):
            sb.remove_head()
            blocks_merged += 1

        return blocks_merged

    def _find_ancestors(self):
        """
        - must run after merge_branches so that duplicate blocks have been
        removed from all branches - otherwise, multiple ancestors will be
        incorrectly identified
        - each branch keeps track of its tail block id (tail_block_id)
        - for each branch:
        1) get branch tail block previous block id and assign it to
            branch.ancestor_block_id to
        2) find the peer branch that contains branch.ancestor_block_id
           and assign it to branch.ancestor_block
        4) get branch.ancestor_block["BlockNum"] and
            assign it to branch.ancestor_block_num
        """
        for branch in self.branches:
            tail_block = branch.blocks.get(branch.tail_block_id)
            if tail_block is not None:
                ancestor_block_id = tail_block["PreviousBlockID"]
                if ancestor_block_id is not None and \
                        ancestor_block_id is not GENESIS_PREVIOUS_BLOCK_ID:
                    ancestor_branches = []
                    for peer_branch in self.branches:
                        ancestor_block = peer_branch.blocks.get(
                            ancestor_block_id, None)
                        if ancestor_block is not None:
                            ancestor_branches.append(peer_branch)
                            branch.ancestor_branch = peer_branch
                            branch.ancestor_branch_id = peer_branch.bcb_id
                            branch.ancestor_block_id = \
                                ancestor_block["Identifier"]
                            branch.ancestor_block_num = \
                                ancestor_block["BlockNum"]
                            branch.ancestor_found = True
                    # if ancestor block id is not GENESIS or None,
                    # then there should be exactly one ancestor branch...
                    if len(ancestor_branches) is 0:
                        # it's possible that there are gaps in the block record
                        branch.ancestor_branch = None
                        branch.ancestor_branch_id = None
                        branch.ancestor_block_id = None
                        branch.ancestor_block_num = None
                        branch.ancestor_found = False
                    if len(ancestor_branches) > 1:
                        raise ValueError("more than one ancestor branch found")
                else:
                    # branch has no ancestor or genesis block ancestor; either
                    # case is valid - set ancestor branch and block id to None
                    branch.ancestor_branch = None
                    branch.ancestor_block_num = None
                    branch.ancestor_found = None

    def _identify_active_branches(self):
        """
        for each branch
            for each block client
                if the branch contains the block clients last block id
                    then the branch is active
                    append the block client id to the active list
                    if it is not already there, append the block client id
                    to the active history list
        note that the branch may be active because of slow validators
        touching the branch far from the head
        """
        for branch in self.branches:
            branch.is_active = False

        for branch in self.branches:
            active_list = []
            for bc in self.block_clients:
                if bc.responding is True:
                    if branch.blocks.get(bc.last_block_id, None) is not None:
                        branch.is_active = True
                        branch.last_active_time = time.time()
                        active_list.append(bc.bc_id)
                        if bc.bc_id not in branch.is_active_history:
                            branch.is_active_history.append(bc.bc_id)
            branch.is_active_list = active_list

    def _find_forks(self):
        '''
        start with active branch with largest block count
        or start with active branch with largest number of validators
        walk the list of ancestors...
        collect the following information for each ancestor:
        ancestor ID, block ID, block numbers
        '''

        # active branches sorted by number of validators, last block count
        branches_ex = []
        for branch in self.branches:
            if branch.is_active:
                branches_ex.append(
                    [branch, branch.is_active_count, branch.block_count])
        sorted_branches_ex = sorted(branches_ex, key=itemgetter(1),
                                    reverse=True)

        forks = []
        for branch in sorted_branches_ex:
            fork = BlockChainFork()
            fork.bcf_id = "fork_{0:07d}".format(len(forks))
            fork.validator_count = branch[0].is_active_count
            fork.build_fork(branch[0])
            forks.append(fork)
        self.forks = forks

    def _find_fork_intercepts(self):
        '''
        create search list comprising all forks in order of validator count
        take largest fork, record as parent.
        check each fork in search list for intercept.
        if intercept, fork is child; calculate fork depth relative to parent,
        record fork depth and parent fork id, and remove from list.
        if no intercept, peer is possible new parent or child of new parent;
        move to next search list, preserving validator count ordering
        repeat on search list until all forks have been processed
        '''

        search_list = list(self.forks)

        while search_list:
            parent_fork = search_list.pop(0)
            parent_fork.is_parent = True
            for_next_search = []
            for fork in search_list:
                if not parent_fork.find_intercept(fork):
                    for_next_search.append(fork)
            search_list = for_next_search

    def trim_empty_branches(self):
        self.branches = [branch for branch in self.branches if
                         branch.block_count is not 0]
        return len(self.branches)

    def _update_stats(self):
        self.bm_stats.validators = len(self.block_clients)
        self.bm_stats.identified = len(self.branches)

        # identify longest branch
        branches = []
        for branch in self.branches:
            branches.append([branch, branch.block_count])
        sorted_branches = sorted(branches, key=itemgetter(1), reverse=True)
        self.bm_stats.longest = 0 \
            if len(sorted_branches) is 0 else sorted_branches[0][1]

        # identify longest active branches
        active_branches = []
        for branch in self.branches:
            if branch.is_active is True:
                active_branches.append([branch, branch.block_count])
        self.bm_stats.active = len(active_branches)

        sorted_active_branches = sorted(
            active_branches, key=itemgetter(1), reverse=True)
        self.bm_stats.longest_active = 0
        self.bm_stats.next_longest_active = 0
        if len(sorted_active_branches) > 0:
            self.bm_stats.sorted_longest_active = active_branches[0][1]
        if len(sorted_active_branches) > 1:
            self.bm_stats.next_longest_active = active_branches[1][1]

        # fork stats
        self.f_stats.validator_count = 0
        self.f_stats.parent_count = 0
        self.f_stats.child_count = 0
        self.f_stats.status = "CONVERGED"
        longest_child_fork_length = 0
        for fork in self.forks:
            self.f_stats.validator_count += fork.validator_count
            if fork.is_parent:
                self.f_stats.parent_count += 1
            else:
                self.f_stats.child_count += 1
                if fork.fork_intercept_length > longest_child_fork_length:
                    longest_child_fork_length = fork.fork_intercept_length
        self.f_stats.longest_child_fork_length = longest_child_fork_length
        self.f_stats.fork_count = len(self.forks)
        if self.f_stats.parent_count > 1:
            self.f_stats.status = "FORKED"
