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

from mktplace.transactions import participant_update


class MockMarketPlaceGlobalStore:
    def __init__(self):
        self.objects = {}
        self.names = {}

    def i2n(self, object_id):
        the_object = self.objects.get(object_id)
        name = the_object.get('name')

        if the_object.get('object-type') == \
                participant_update.ParticipantObject.ObjectTypeName:
            return '//{0}'.format(name)

        return name

    def n2i(self, name):
        return self.names.get(name)

    def bind(self, name, object_id):
        self.names[name] = object_id

    def __setitem__(self, object_id, the_object):
        self.objects[object_id] = the_object
