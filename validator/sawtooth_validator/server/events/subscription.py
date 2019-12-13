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
import re

from sawtooth_validator.protobuf import events_pb2


class EventSubscription:
    """Represents a subscription to events. An event is part of a subscription
    if its type matches the type of the subscription and, if any filters are
    included in the subscription, it passes all filters.
    """

    def __init__(self, event_type, filters=None):
        self.event_type = event_type
        if filters:
            self.filters = filters
        else:
            self.filters = []

    def __eq__(self, other):
        if self.event_type != other.event_type:
            return False

        for f in self.filters:
            if f not in other.filters:
                return False

        return True

    def __contains__(self, event):
        """Returns whether this events belongs within this subscriptions."""
        if event.event_type == self.event_type:
            for sub_filter in self.filters:
                if event not in sub_filter:
                    return False
            return True

        return False


class InvalidFilterError(Exception):
    pass


class EventFilterFactory:
    def __init__(self):
        self.filter_types = {
            events_pb2.EventFilter.SIMPLE_ANY: SimpleAnyFilter,
            events_pb2.EventFilter.SIMPLE_ALL: SimpleAllFilter,
            events_pb2.EventFilter.REGEX_ANY: RegexAnyFilter,
            events_pb2.EventFilter.REGEX_ALL: RegexAllFilter,
        }

    def create(self, key, match_string,
               filter_type=events_pb2.EventFilter.SIMPLE_ANY):
        try:
            return self.filter_types[filter_type](key, match_string)
        except KeyError:
            raise InvalidFilterError(
                "Unknown filter type: {}".format(filter_type))


class EventFilter(metaclass=ABCMeta):
    """Represents a subset of events within an event type."""

    def __init__(self, key, match_string):
        self.match_string = match_string
        self.key = key

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return self.key == other.key \
            and self.match_string == other.match_string

    def __contains__(self, event):
        return self.matches(event)

    @abstractmethod
    def matches(self, event):
        """Returns whether the event passes this filter."""
        raise NotImplementedError()


class SimpleAnyFilter(EventFilter):
    def matches(self, event):
        for attribute in event.attributes:
            if self.key == attribute.key:
                if self.match_string == attribute.value:
                    return True
        return False


class SimpleAllFilter(EventFilter):
    def matches(self, event):
        for attribute in event.attributes:
            if self.key == attribute.key:
                if self.match_string != attribute.value:
                    return False
        return True


class RegexAnyFilter(EventFilter):
    """Represents a subset of events within an event type. Pattern must be a
    valid regular expression that can be compiled by the re module.

    Since multiple event attributes with the same key can be present in an
    event, an event is considered part of this filter if its pattern matches
    the value of ANY attribute with the filter's key.

    For example, if an event has the following attributes:

        - Attribute(key="address", value="abc")
        - Attribute(key="address", value="def")

    it will pass the following filter:

        AnyRegexFilter(key="address", value="abc")

    Because it matches one of the two attributes with the key "address".
    """

    def __init__(self, key, match_string):
        super().__init__(key, match_string)
        try:
            self.regex = re.compile(match_string)
        except Exception as e:
            raise InvalidFilterError(
                "Invalid regular expression: {}: {}".format(
                    match_string, str(e)))

    def matches(self, event):
        for attribute in event.attributes:
            if self.key == attribute.key:
                if self.regex.search(attribute.value):
                    return True
        return False


class RegexAllFilter(EventFilter):
    """Represents a subset of events within an event type. Pattern must be a
    valid regular expression that can be compiled by the re module.

    Since multiple event attributes with the same key can be present in an
    event, an event is considered part of this filter if its pattern matches
    the value of ALL attribute with the filter's key.

    For example, if an event has the following attributes:

        - Attribute(key="address", value="abc")
        - Attribute(key="address", value="def")

    it will NOT pass this filter:

        AllRegexFilter(key="address", value="abc")

    Because it does not match all attributes with the key "address".
    """

    def __init__(self, key, match_string):
        super().__init__(key, match_string)
        try:
            self.regex = re.compile(match_string)
        except Exception as e:
            raise InvalidFilterError(
                "Invalid regular expression: {}: {}".format(
                    match_string, str(e)))

    def matches(self, event):
        for attribute in event.attributes:
            if self.key == attribute.key:
                if not self.regex.search(attribute.value):
                    return False
        return True
