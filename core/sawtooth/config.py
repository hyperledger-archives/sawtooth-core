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

import os
import re
import json


class ConfigFileNotFound(Exception):
    """Exception thrown when config files are expected but not found."""

    def __init__(self, config_files, search_path):
        super(ConfigFileNotFound, self).__init__(self)
        self.config_files = config_files
        self.search_path = search_path

    def __str__(self):
        return ("Unable to locate the following configuration files: " +
                "{0} (search path: {1})".format(", ".join(self.config_files),
                                                ", ".join(self.search_path)))


class InvalidSubstitutionKey(Exception):
    """Exception raised when a config uses invalid substitution key."""

    def __init__(self, key, config_key, config_value, source):
        super(InvalidSubstitutionKey, self).__init__(self)
        self.key = key
        self.config_key = config_key
        self.config_value = config_value
        self.source = source

    def __str__(self):
        text = ("invalid substitution key of " + self.key + " for " +
                self.config_key + " with value '" + self.config_value + "'")
        if self.source is not None:
            text = text + " in " + self.source
        return text


class Config(dict):
    """Configuration base class."""

    def __init__(self, name="config", cfg=None, source=None, **kwargs):
        super(Config, self).__init__(**kwargs)

        if cfg is None:
            cfg = {}

        self.name = name
        self.update(cfg)
        self._source = source

        # The maximum number of times substitutions should be performed
        # during resolve().
        self.substitution_max_iterations = 10

    def get_source(self, key):
        """Returns the source of the key."""

        return self._source

    def resolve(self, substitutions):
        """Performs path substitutions, as provided, and then returns
        a dict of key/value pairs.

        Keyword arguments:
        substitutions -- a dict where the key is the variable to be
        substituted and the value is the config key to use to
        lookup the value
        """

        pathsubs = {}
        for key, value in substitutions.iteritems():
            if value in self:
                pathsubs[key] = self[value]

        cfg = {}
        for key, value in self.iteritems():
            if isinstance(value, basestring):
                for _ in xrange(self.substitution_max_iterations):
                    try:
                        new_value = value.format(**pathsubs)
                    except KeyError, e:
                        raise InvalidSubstitutionKey(
                            str(e), key, value, self.get_source(key))
                    if new_value == value:
                        break
                    value = new_value
            cfg[key] = value

        return cfg


class EnvConfig(Config):
    """Configuration based on environment variables."""

    def __init__(self, env_to_config_list):
        super(EnvConfig, self).__init__(name="env")

        self._source_data = {}

        for (env_key, config_key) in env_to_config_list:
            if env_key in os.environ:
                self[config_key] = os.environ[env_key]
                self._source_data[config_key] = env_key

    def get_source(self, key):
        return self.name + ":" + self._source_data[key]


class ArgparseOptionsConfig(Config):
    """Configuration based on argparse options."""

    def __init__(self, option_to_config_list, options):
        super(ArgparseOptionsConfig, self).__init__(name="cli")

        options_dict = vars(options)

        for (option_key, config_key) in option_to_config_list:
            if (option_key in options_dict.keys()
                    and options_dict[option_key] is not None):
                self[config_key] = options_dict[option_key]


class JsonConfig(Config):
    """Loads configuration from a JSON file given the file content."""

    def __init__(self, lines, filename=None):
        super(JsonConfig, self).__init__()

        if filename is not None:
            self.name = "json:" + filename
        else:
            self.name = "json"

        self._parse(lines)

    def _parse(self, lines):
        cpattern = re.compile('##.*$')

        text = ""
        for line in lines:
            text += re.sub(cpattern, '', line) + ' '

        self.update(json.loads(text))


class JsonFileConfig(Config):
    """Loads configuration from a JSON file given a filename."""

    def __init__(self, filename):
        super(JsonFileConfig, self).__init__(name="file:" + filename)

        with open(filename) as fd:
            lines = fd.readlines()
        cfg = JsonConfig(lines, filename)
        self.update(cfg)


class AggregateConfig(Config):
    """Aggregates multiple Configs by applying them in order."""

    def __init__(self, configs):
        super(AggregateConfig, self).__init__(name="aggregate")

        self._source_data = {}

        for config in configs:
            for key, value in config.iteritems():
                self[key] = value
                self._source_data[key] = config.get_source(key)

    def get_source(self, key):
        return self._source_data[key]


def load_config_files(config_files, search_path, config_files_required=True):
    """Loads a set of config files from a search path.

    Keyword arguments:
    config_files -- a list of config filenames
    search_path -- a list of directories to search
    config_files_required -- if True, ConfigFilesNotFound is thrown if
    the configuration files cannot be located
    """
    files_not_found = []
    files_found = []

    for cfile in config_files:
        filename = None
        for directory in search_path:
            if os.path.isfile(os.path.join(directory, cfile)):
                filename = os.path.join(directory, cfile)
                break

        if filename is None:
            files_not_found.append(cfile)
        else:
            files_found.append(filename)

    if config_files_required and len(files_not_found) > 0:
        raise ConfigFileNotFound(files_not_found, search_path)

    config_list = []
    for filename in files_found:
        config_list.append(JsonFileConfig(filename))
    return config_list
