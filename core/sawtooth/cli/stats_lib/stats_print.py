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

from sawtooth.cli.stats_lib.stats_utils import StatsModule

from sawtooth.cli.stats_lib.validator_stats import ValidatorStatsManager
from sawtooth.cli.stats_lib.validator_stats import SystemStatsManager

from sawtooth.cli.stats_lib.platform_stats import PlatformStatsManager
from sawtooth.cli.stats_lib.fork_detect import BranchManager
from sawtooth.cli.stats_lib.topology_stats import TopologyManager

from sawtooth.cli.stats_lib.print_views import SummaryView

from sawtooth.cli.stats_lib.print_views import GeneralView
from sawtooth.cli.stats_lib.print_views import PlatformView
from sawtooth.cli.stats_lib.print_views import ConsensusView
from sawtooth.cli.stats_lib.print_views import PacketView
from sawtooth.cli.stats_lib.print_views import NetworkView
from sawtooth.cli.stats_lib.print_views import TransactionView
from sawtooth.cli.stats_lib.print_views import BranchView
from sawtooth.cli.stats_lib.print_views import ForkView

CURSES_IMPORTED = True
try:
    import curses
except ImportError:
    CURSES_IMPORTED = True if CURSES_IMPORTED else False


class ConsolePrint(object):

    def __init__(self):
        self.use_curses = False
        self.start = True
        self.scrn = None

        if self.use_curses:
            self.scrn = curses.initscr()

            curses.noecho()
            curses.cbreak()

            self.scrn.nodelay(1)

    def cpprint(self, print_string, finish=False, reverse=False):
        if self.use_curses:
            try:
                attr = curses.A_NORMAL
                if reverse:
                    attr = curses.A_REVERSE
                if self.start:
                    self.scrn.erase()
                    self.start = False
                hw = self.scrn.getmaxyx()
                pos = self.scrn.getyx()
                if pos[0] < hw[0] and pos[1] == 0:
                    print_string = print_string[:hw[1] - 1]
                    self.scrn.addstr(print_string, attr)
                    if pos[0] + 1 < hw[0]:
                        self.scrn.move(pos[0] + 1, 0)
                if finish:
                    self.scrn.refresh()
                    self.start = True
            except curses.CursesError as e:
                # show curses errors at top of screen for easier debugging
                self.scrn.move(0, 0)
                self.scrn.addstr("{} {} {} {}\n".format(type(e), e, pos, hw),
                                 attr)
                self.scrn.addstr(print_string + "\n", attr)
        else:
            print(print_string)

    def cpstop(self):
        if self.use_curses:
            curses.nocbreak()
            self.scrn.keypad(0)
            curses.echo()
            curses.endwin()
            print("print manager ended curses window")


class StatsPrintManager(StatsModule):

    def __init__(self, epm, config):
        super(StatsPrintManager, self).__init__()
        self.config = config

        self._console_print = ConsolePrint()

        self.platform_stats = None
        self.branch_manager = None
        self.system_stats = None
        self.topology_stats = None
        self.stats_clients = None

        self._summary_view = None
        self._view_options = None
        self._view_mode = None
        self._current_view = None

        self.print_all = False

    def initialize(self, module_list):
        self.module_list = module_list
        system_stats_manager = self.get_module(SystemStatsManager)
        topology_stats_manager = self.get_module(TopologyManager)
        validator_stats_manager = self.get_module(ValidatorStatsManager)
        self.platform_stats = self.get_module(PlatformStatsManager)
        self.branch_manager = self.get_module(BranchManager)

        self.system_stats = system_stats_manager.system_stats
        self.topology_stats = topology_stats_manager.topology_stats
        self.stats_clients = validator_stats_manager.clients

        self._summary_view = SummaryView(self._console_print, self)

        self._view_options = self._initialize_views()
        view_option = self._view_options.get(ord('g'))  # general view
        self._view_mode = view_option[0]  # 'general'
        self._current_view = view_option[1]  # GeneralView instance

        self.update_config(self.config)

    def report(self):
        self._print_stats()

    def stop(self):
        self._console_print.cpstop()

    def _print_stats(self):
        self._check_view()
        self._summary_view.print_summary(self._view_mode)
        if self.print_all:
            self._print_all_views()
        else:
            self._current_view.print_view()
        self._console_print.cpprint("", True)

    def _check_view(self):
        char_buffer = ''
        if self._console_print.scrn:
            char_buffer = self._console_print.scrn.getch()

        view_option = self._view_options.get(char_buffer)

        if view_option is not None:
            self._view_mode = view_option[0]
            self._current_view = view_option[1]
            # assert self._view_mode == 'general'

    def _initialize_views(self):
        view_options = {
            ord('g'): ["general", GeneralView(
                self._console_print, self.stats_clients)],
            ord('p'): ["platform", PlatformView(
                self._console_print, self.stats_clients)],
            ord('c'): ["consensus", ConsensusView(
                self._console_print, self.stats_clients)],
            ord('n'): ["network", NetworkView(
                self._console_print, self.stats_clients)],
            ord('t'): ["transaction", TransactionView(
                self._console_print, self.stats_clients)],
            ord('k'): ["packet", PacketView(
                self._console_print, self.stats_clients)],
            ord('b'): ["branch", BranchView(
                self._console_print, self.branch_manager)],
            ord('f'): ["fork", ForkView(
                self._console_print, self.branch_manager)]
        }
        return view_options

    def update_config(self, config):
        stats_print_config = config.get('StatsPrint', None)
        if stats_print_config is None:
            return
        else:
            if stats_print_config.get('print_all', False):
                self.print_all = True

    def _print_all_views(self):
        self._console_print.use_curses = False
        for value in self._view_options.values():
            value[1].print_view()
