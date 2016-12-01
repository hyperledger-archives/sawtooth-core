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

from collections import OrderedDict
import ConfigParser
from datetime import datetime
import getpass
import os
import yaml


class ListWriter(object):
    """
    used in the list subcommands
    """
    def __init__(self, state, obj_type, full=False, will_print_yaml=False):
        self._state = state
        self._obj_type = obj_type
        self._objects = []
        if not will_print_yaml:
            self._lengths = self._calc_field_lengths()
            self._full = full
            self._fields = []
            self._calc_fields()
            self._fmt_string = self._calc_fmt_string()
        else:
            for _, obj in self._state.iteritems():
                if obj.get('object-type') == self._obj_type:
                    self._objects.append(hyphen_to_camelcase_on_dict(obj))
        self._yaml = will_print_yaml

    def _calc_fmt_string(self):
        return " ".join(
            ["{:<%d}" % (self._lengths[k] + 2) for k in self._fields])

    def _lookup_nice_name(self, obj):
        for att, val in obj.iteritems():
            if att == 'timestamp':
                obj[att] = datetime.utcfromtimestamp(val).strftime("%x %X")
            elif att == 'corporate-debt-ratings':
                obj[att] = " ".join(["{}:{}".format(ag, r)
                                     for ag, r in val.iteritems()])
            elif att == 'authorization':
                new_val = []
                for auth in val:
                    user_obj = self._state.get(auth.get('participant-id'))
                    new_val.append("{}:{}".format(user_obj.get('username'),
                                                  auth.get('role')))
                obj[att] = " ".join(new_val)
            elif att == 'holdings':
                new_val = []
                for h in val:
                    holding_obj = self._state.get(h)
                    new_val.append("{}".format(holding_obj.get('asset-type')))
                obj[att] = ",".join(new_val)

    def _calc_field_lengths(self):
        lengths = {}
        for _, obj in self._state.iteritems():
            if obj.get('object-type') == self._obj_type:
                obj = obj.copy()
                self._lookup_nice_name(obj)
                obj = hyphen_to_camelcase_on_dict(obj)
                self._objects.append(obj)
                for attr, val in obj.iteritems():
                    try:
                        lengths[attr]
                    except KeyError:
                        lengths[attr] = len(str(val))
                    if lengths[attr] < len(str(val)):
                        lengths[attr] = len(str(val))
                    if lengths[attr] < len(attr):
                        lengths[attr] = len(attr)
        return lengths

    def _calc_fields(self):
        for k, v in self._lengths.iteritems():
            if v < 30 or self._full:
                self._fields.append(k)

    def write(self, field=None, field_val=None):
        if self._yaml:
            if field is not None and field_val is not None:
                objects_to_yaml = []
                for item in self._objects:
                    if item.get(field) == field_val:
                        objects_to_yaml.append(item)
                if len(objects_to_yaml) != 0:
                    print yaml.dump(objects_to_yaml, default_flow_style=False)
                return
            if len(self._objects) != 0:
                print yaml.dump(self._objects, default_flow_style=False)
            return
        print self._fmt_string.format(*self._fields)
        for obj in self._objects:
            if field is not None and field_val is not None:
                if obj.get(field) == field_val:
                    print self._fmt_string.format(
                        *[obj.get(k) or "N/A"
                          for k in self._fields])
            else:
                print self._fmt_string.format(
                    *[obj.get(k) or "N/A"
                      for k in self._fields])


class ShowWriter(object):
    """Prints out the dict obj in stacked k : v pairs"""
    def __init__(self, obj, obj_type, key):
        self._key = key
        self._obj = hyphen_to_camelcase_on_dict(obj) if \
            obj is not None else None
        self._obj_type = obj_type
        self._fmt_string = self.calc_fmt_string(self._obj)

    def calc_fmt_string(self, obj):
        lengths = {'key': 0, 'value': 0}
        if obj is not None:
            for k, v in obj.iteritems():
                if lengths['key'] < len(str(k)):
                    lengths['key'] = len(str(k))
                if not isinstance(v, dict) and \
                        not isinstance(v, list):
                    if lengths['value'] < len(str(v)):
                        lengths['value'] = len(str(v))
                elif isinstance(v, list):
                    if len(v) > 0:
                        if lengths['value'] < len(str(v[0])):
                            lengths['value'] = len(str(v[0]))
                elif isinstance(v, dict):
                    for ik, iv in v.iteritems():
                        if lengths['value'] < len(str(ik) + str(iv)):
                            lengths['value'] = len(str(ik) + str(iv))
                else:
                    pass
            return "{:<%d}: {:<%d}" % (lengths['key'], lengths['value'])
        else:
            return None

    def write(self, indent=False):
        if self._obj is not None:
            for k, v in self._obj.iteritems():
                if isinstance(v, str) or isinstance(v, float) or \
                        isinstance(v, int):
                    if indent:
                        print "----{}".format(self._fmt_string.format(k, v))
                    else:
                        print self._fmt_string.format(k, v)
                elif isinstance(v, dict):
                    print k + ':'
                    ShowWriter(v, None, None).write(indent=True)
                else:
                    print k + ":"
                    for item in v:
                        if isinstance(item, dict):
                            ShowWriter(item, None, None).write(indent=True)
                        else:
                            print "----{}".format(item)

        else:

            print "{} with identifier {} could not be found.".format(
                self._obj_type, self._key)


def try_get_then_lookup(store, obj_type, indexes, key):
    try:
        obj = store[key]
        if obj["object-type"] == obj_type:
            return obj
    except KeyError:
        pass
    org_list = [x[1] for x in store.iteritems() if
                x[1]["object-type"] == obj_type]
    for obj in org_list:
        for index in indexes:
            idx = index.split(":")[1]
            try:
                if obj[idx] == key:
                    return obj
            except KeyError:
                pass
    return None


def hyphen_to_camelcase_on_dict(obj):
    serialized = {}
    for attr in obj.iterkeys():
        # key is attr converted from
        key = ''.join(w.capitalize() for w in attr.split('-'))
        if obj.get(attr) is not None:
            if isinstance(obj.get(attr), OrderedDict):
                serialized[key] = hyphen_to_camelcase_on_dict(obj.get(attr))
            elif isinstance(obj.get(attr), list):
                serialized[key] = []
                for item in obj.get(attr):
                    if isinstance(item, OrderedDict):
                        serialized[key].append(
                            hyphen_to_camelcase_on_dict(item))
                    else:
                        serialized[key].append(item)
            else:
                serialized[key] = obj.get(attr)
    return serialized


def change_config(key, value):
    home = os.path.expanduser("~")
    config_file = os.path.join(home, ".sawtooth", "bond.cfg")
    config = ConfigParser.SafeConfigParser()
    if os.path.exists(config_file):
        config.read(config_file)
    config.set("DEFAULT", key, value)
    save_config(config)


def save_config(config):
    home = os.path.expanduser("~")

    config_file = os.path.join(home, ".sawtooth", "bond.cfg")
    if not os.path.exists(os.path.dirname(config_file)):
        os.makedirs(os.path.dirname(config_file))

    with open("{}.new".format(config_file), "w") as fd:
        config.write(fd)
    os.rename("{}.new".format(config_file), config_file)


def change_wif_and_addr_filename(key_dir, old_username, new_username):
    os.rename(os.path.join(key_dir, old_username + ".wif"),
              os.path.join(key_dir, new_username + ".wif"))
    os.rename(os.path.join(key_dir, old_username + ".addr"),
              os.path.join(key_dir, new_username + ".addr"))


def load_config():
    home = os.path.expanduser("~")
    real_user = getpass.getuser()

    config_file = os.path.join(home, ".sawtooth", "bond.cfg")
    key_dir = os.path.join(home, ".sawtooth", "keys")

    config = ConfigParser.SafeConfigParser()
    config.set('DEFAULT', 'url', 'http://localhost:8800')
    config.set('DEFAULT', 'key_dir', key_dir)
    config.set('DEFAULT', 'username', real_user)
    config.set('DEFAULT', 'key_file', '%(key_dir)s/%(username)s.wif')

    if os.path.exists(config_file):
        config.read(config_file)
    else:
        save_config(config)
    return config
