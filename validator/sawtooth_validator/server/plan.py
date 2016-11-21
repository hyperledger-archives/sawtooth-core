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


class TransactionExecutionPlan(object):
    def __init__(self):
        self.root = None


class TransactionExecutionPlanNode(object):
    def __init__(self, txn_id, dependencies):
        self.txn_id = txn_id
        self.dependencies = dependencies


class SerialExecutionPlanGenerator(object):
    def generate_plan(self, txns):
        plan = TransactionExecutionPlan()

        i = 0
        last_node = None
        for txn in txns:
            node = TransactionExecutionPlanNode(
                txn_id=txn.signature,
                dependencies=[last_node])
            last_node = node

            if i == 0:
                plan.root = node
            i += 1

        return plan
