#!/usr/bin/python

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
import sys
import warnings
import logging
import logging.handlers

from colorlog import ColoredFormatter


def _append_real_path(path):
    return sys.path.append(os.path.realpath(path))


_append_real_path(os.path.join(os.path.dirname(__file__), ".."))
_append_real_path(os.path.join(os.path.dirname(__file__), "..", ".."))
_append_real_path(os.path.join(os.path.dirname(__file__), "..", "lib"))

import re
from string import Template

from gossip.common import json2dict


def ParseConfigurationFiles(cfiles, search_path, variable_map=None):
    """
    Locate and parse a collection of configuration files stored in a
    modified JSON format.

  :param list(str) cfiles: list of configuration files to load
  :param list(str) search_path: list of directores where the files
         may be located
  :param dict variable_map: a set of substitutions for variables in the files
  :return dict:an aggregated dictionary of configuration information
    """
    config = {}
    files_found = []
    files_not_found = []

    for cfile in cfiles:
        filename = None
        if os.path.isabs(cfile):
            filename = cfile if os.path.isfile(cfile) else None
        else:
            for directory in search_path:
                if os.path.isfile(os.path.join(directory, cfile)):
                    filename = os.path.join(directory, cfile)
                    break

        if filename is None:
            files_not_found.append(cfile)
        else:
            files_found.append(filename)

    if len(files_not_found) > 0:
        path_str = ", ".join(map(os.path.realpath, search_path))
        warnings.warn(
            "Unable to locate the following configuration files: {0} "
            "(search path: {1})".format(", ".join(files_not_found),
                                        path_str))
        sys.exit(-1)

    for filename in files_found:
        try:
            config.update(ParseConfigurationFile(filename, variable_map))
        except IOError as detail:
            warnings.warn(
                ("Error parsing configuration file %s; IO error %s" %
                    (filename, str(detail))))
            sys.exit(-1)
        except ValueError as detail:
            warnings.warn(
                ("Error parsing configuration file %s; value error %s" %
                    (filename, str(detail))))
            sys.exit(-1)
        except NameError as detail:
            warnings.warn(
                ("Error parsing configuration file %s; name error %s" %
                    (filename, str(detail))))
            sys.exit(-1)
        except KeyError as detail:
            warnings.warn(
                ("Error parsing configuration file %s; key error %s" %
                    (filename, str(detail))))
            sys.exit(-1)
        except:
            warnings.warn(
                ('Error parsing configuration file %s; %s' %
                    (filename, sys.exc_info()[0])))
            sys.exit(-1)

    return config


def ParseConfigurationFile(filename, variable_map):
    """
    Parse a configuration file expanding variable references
    using the Python Template library (variables are $var format)

  :param string filename: name of the configuration file
  :param dict variable_map: dictionary of expansions to use
  :returns dict: dictionary of configuration information
    """
    cpattern = re.compile('##.*$')

    with open(filename) as fp:
        lines = fp.readlines()

    text = ""
    for line in lines:
        text += re.sub(cpattern, '', line) + ' '

    if variable_map:
        text = Template(text).substitute(variable_map)

    return json2dict(text)


def SetupLoggers(config):
    loglevel = (getattr(logging, config["LogLevel"])
                if 'LogLevel' in config else logging.WARN)
    logger = logging.getLogger()
    logger.setLevel(loglevel)

    if 'LogFile' in config and config['LogFile'] != '__screen__':
        logfile = config['LogFile']
        if not os.path.isdir(os.path.dirname(logfile)):
            warnings.warn("Logging directory {0} does not exist".format(
                os.path.abspath(os.path.dirname(logfile))))
            sys.exit(-1)

        flog = logging.handlers.RotatingFileHandler(logfile,
                                                    maxBytes=2 * 1024 * 1024,
                                                    backupCount=1000,
                                                    mode='a')
        flog.setFormatter(logging.Formatter(
            '[%(asctime)s, %(levelno)d, %(module)s] %(message)s', "%H:%M:%S"))
        logger.addHandler(flog)
    else:
        clog = logging.StreamHandler()
        formatter = ColoredFormatter(
            "%(log_color)s[%(asctime)s %(levelname)-8s%(module)s]%(reset)s "
            "%(white)s%(message)s",
            datefmt="%H:%M:%S",
            reset=True,
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red',
            }
        )

        # clog.setFormatter(logging.Formatter('[%(name)s] %(message)s'))
        # clog.setLevel(loglevel)
        clog.setFormatter(formatter)
        logger.addHandler(clog)

    # process all overrides
    logoverride = config.get("LogOverride", {})
    for modname, modlevel in logoverride.iteritems():
        modlogger = logging.getLogger(modname)
        modlogger.setLevel(getattr(logging, modlevel))
