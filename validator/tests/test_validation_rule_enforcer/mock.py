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


class MockSettingsViewFactory:
    def __init__(self):
        self.settings = {}

    def create_settings_view(self, root):
        return MockSettingsView(self.settings)

    def add_setting(self, setting, value):
        self.settings[setting] = value


class MockSettingsView:
    def __init__(self, settings):
        self.settings = settings

    def get_setting(self, setting):
        return self.settings.get(setting)
