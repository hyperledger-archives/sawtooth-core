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
# ------------------------------------------------------------------------------

import abc


class TransactionHandler(object, metaclass=abc.ABCMeta):
    """
    TransactionHandler is the Abstract Base Class that defines the business
    logic for a new transaction family.

    The family_name, family_versions, and namespaces properties are
    used by the processor to route processing requests to the handler.
    """

    @abc.abstractproperty
    def family_name(self):
        """
        family_name should return the name of the transaction family that this
        handler can process, e.g. "intkey"
        """
        pass

    @abc.abstractproperty
    def family_versions(self):
        """
        family_versions should return a list of versions this transaction
        family handler can process, e.g. ["1.0"]
        """
        pass

    @abc.abstractproperty
    def namespaces(self):
        """
        namespaces should return a list containing all the handler's
        namespaces, e.g. ["abcdef"]
        """
        pass

    @abc.abstractmethod
    def apply(self, transaction, context):
        """
        Apply is the single method where all the business logic for a
        transaction family is defined. The method will be called by the
        transaction processor upon receiving a TpProcessRequest that the
        handler understands and will pass in the TpProcessRequest and an
        initialized instance of the Context type.
        """
        pass
