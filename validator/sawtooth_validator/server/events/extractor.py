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

from abc import ABCMeta
from abc import abstractmethod


class EventExtractor(metaclass=ABCMeta):
    """Construct all the events of interest by taking the union of all
    subscriptions. One extractor should be created for each input source that
    events can be extracted from. This input source should be passed to the
    implementation through the constructor.
    """

    @abstractmethod
    def extract(self, subscriptions):
        """Produce events for the given subscriptions.

        Args:
            subscriptions (list of :obj:`EventSubscription`): The subscriptions
            to return events for.

        Returns:
            A list of protobuf Events.
        """
        raise NotImplementedError()
