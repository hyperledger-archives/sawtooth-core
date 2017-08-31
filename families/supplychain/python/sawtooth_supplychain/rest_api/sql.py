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
# -----------------------------------------------------------------------------


class SqlBuilder:
    """Simple class for constructing variable SQL statements.
    """
    def __init__(self, *sql_fragments):
        """Constructs a new SqlBuilder, with the given fragments.

        Args:
            sql_fragments: a list of sql fragments, either `str` or SqlBuilder
                objects.
        """
        self._sql_fragments = list(sql_fragments)

    def add(self, fragment):
        """Add a new fragment to the builder.

        Args:
            fragment (str|:obj:`SqlBuilder`) the fragment to add to the
                builder.
        """
        self._sql_fragments.append(fragment)

    def build(self):
        """Builds the SQL statement from the collected fragments.

        Returns:
            str - the resulting SQL Statement
        """
        return " ".join([str(fragment) for fragment in self._sql_fragments])

    def __str__(self):
        return self.build()
