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

# Supply Chain REST API

import logging
import json
import re
import psycopg2
import psycopg2.extras
import aiopg
from aiohttp import web

from sawtooth_supplychain.rest_api.sql import SqlBuilder
import sawtooth_supplychain.rest_api.exceptions as errors


DEFAULT_TIMEOUT = 300
LOGGER = logging.getLogger(__name__)
DEFAULT_PAGE_SIZE = 200
NO_ROWS_RETURNED = -1


class RouteHandler(object):
    """Contains a number of aiohttp handlers for endpoints in
    the Supply Chain Rest Api.

    Each handler takes an aiohttp Request object, and uses the data in
    that request to create queries to send to the database. The query
    results are processed, and finally an aiohttp Response object is
    sent back to the client with JSON formatted data and metadata.

    If something goes wrong, an aiohttp HTTP exception is raised.

    Args:
        loop (:obj: `asyncio.EventLoop`) the event loop
        rest_api_config (:obj:`RestApiConfig`) the configuration
    """
    def __init__(self, loop, rest_api_config):
        self._loop = loop
        self._config = rest_api_config

    async def list_agents(self, request):
        """Fetches a paginated list of all Agents. Using the name filter
        parameter narrows the list to any Agents who have a name which
        contains a specified case-insensitive string.

        Request:
            query:
                - name: a partial name to filter Agents by
                - count: Number of items to return
                - page: page number, relative to the count
                - head: the block_num to use as head for the purpose of
                        retrieving Agents

        Response:
            data: JSON array of Agents
            paging: paging info and nav (e.g. next link )
        """

        # Get query parameters
        name = request.url.query.get('name', None)

        count, page_num = RouteHandler._extract_paging_params(request)

        head = await self._get_block_num_for_request(request)

        base_where_clause = \
            SqlBuilder('WHERE %s >= start_block_num AND %s <= end_block_num ')

        base_query_variables = (head, head)
        if name:
            base_where_clause.add('AND name LIKE %s')
            base_query_variables += ('%{}%'.format(name),)

        where_clause = base_where_clause
        page_clause = 'LIMIT %s OFFSET %s'
        query_variables = base_query_variables + (count, page_num * count)

        query = SqlBuilder('SELECT id, identifier, name FROM agent ',
                           where_clause,
                           page_clause).build()

        rows = await self._db_query(query, query_variables)
        fields = ('id', 'identifier', 'name')
        data = self._rows_to_dicts(fields, rows)

        count_query = SqlBuilder('SELECT COUNT(*) FROM agent ',
                                 base_where_clause).build()
        return await self._generate_paginated_response(
            request,
            count_query, base_query_variables,
            page_num, count, head, data)

    async def fetch_agent(self, request):
        """Fetches a specific agent, by identifier.

        Request:
            query:
                - agent_id: the identifier of the agent to fetch
                - head: the block_num to use as head for the purpose of
                        retrieving the Agent

        Response:
            data: JSON response with Agent data
        """

        agent_id = request.match_info.get('agent_id', '')
        head = await self._get_block_num_for_request(request)

        # Create query
        query = ('SELECT identifier, name '
                 'FROM agent '
                 'WHERE %s >= start_block_num AND %s <= end_block_num '
                 'AND identifier = %s;')
        query_tuple = (head, head, agent_id)

        rows = await self._db_query(query, query_tuple)

        if len(rows) > 1:
            LOGGER.exception("Too many rows returned.")
            raise errors.UnknownDatabaseError()

        elif len(rows) == 1:
            # Return the data
            fields = ('identifier', 'name')
            data = self._rows_to_dicts(fields, rows).pop()

            return self._wrap_response(
                request,
                data=data,
                metadata={'head': head})

        else:
            raise errors.AgentNotFound()

    async def list_applications(self, request):
        """Fetches the data for the current set of Applications

        Request:
            query:
                - applicant: the public key of the applicant Agent to filter by
                - status: An application status to filter by
                - count: Number of items to return
                - page: page number, relative to the count
                - head: the block_num to use as head for the purpose of
                        retrieving Applications

        Response:
            data: JSON response with array of Applications
            head: the head value provided, or implied
            paging: paging info and nav (e.g. next link )
        """

        # Get query parameters
        applicant = request.url.query.get('applicant', None)
        status = request.url.query.get('status', None)

        count, page_num = RouteHandler._extract_paging_params(request)
        head = await self._get_block_num_for_request(request)

        # Create query
        base_where_clause = SqlBuilder(
            'WHERE %s >= start_block_num AND %s <= end_block_num '
            'AND a.type = t.id AND a.status = s.id')

        base_query_variables = (head, head)

        if applicant is not None:
            base_where_clause.add('AND a.applicant = %s')
            base_query_variables += (applicant,)

        if status is not None:
            base_where_clause.add('AND s.name = %s')
            base_query_variables += (status.upper(),)

        query = SqlBuilder(
            'SELECT '
            'a.record_identifier as recordIdentifier, '
            'a.applicant as applicant, '
            't.name as type, '
            's.name as status, '
            'a.terms as terms '
            'FROM application a, status_enum s, type_enum t ',
            base_where_clause,
            ' LIMIT %s OFFSET %s').build()
        query_variables = base_query_variables + (count, page_num * count)

        rows = await self._db_query(query, query_variables)

        fields = ('recordIdentifier', 'applicant',
                  'type', 'status', 'terms')
        data = self._rows_to_dicts(fields, rows)

        for app in data:
            app['status'].strip()
            app['type'].strip()

        count_query = SqlBuilder(
            'SELECT COUNT(a.*) '
            'FROM application a, status_enum s, type_enum t ',
            base_where_clause).build()
        return await self._generate_paginated_response(
            request,
            count_query, base_query_variables,
            page_num, count, head, data)

    async def list_records(self, request):
        """Fetches the data for the current set of Records

        Request:
            query:
                - identifier: A partial identifier to filter Records by
                - count: Number of items to return
                - page: page number, relative to the count
                - head: the block_num to use as head for the purpose of
                        retrieving Applications

        Response:
            data: JSON response with array of Records
            head: the head value provided, or implied
            paging: paging info and nav (e.g. next link )
        """

        # Get query parameters
        identifier = request.url.query.get('identifier', None)

        count, page_num = RouteHandler._extract_paging_params(request)
        head = await self._get_block_num_for_request(request)

        # Create query
        base_where_clause = SqlBuilder(
            'WHERE record.start_block_num <= %s AND '
            'record.end_block_num >= %s ')

        base_query_variables = (head, head)
        if identifier is not None:
            base_where_clause.add('AND record.identifier LIKE %s')
            identifier = "%" + identifier + "%"
            base_query_variables += (identifier,)

        # Get a connection and cursor
        query = SqlBuilder(
            'SELECT id, identifier, creation_time, finalize '
            'FROM record ',
            base_where_clause,
            'LIMIT %s OFFSET %s').build()
        query_variables = base_query_variables + (count, page_num)

        rows = await self._db_query(query, query_variables)

        # Get the owners for each record
        owners = []
        for row in rows:
            record_id = row['id']
            query = ("SELECT agent_identifier, start_time "
                     "FROM record_agent "
                     "INNER JOIN type_enum ON record_agent.agent_type = "
                     "type_enum.id WHERE record_agent.record_id = %s "
                     "AND type_enum.name='OWNER';")

            query_tuple = (record_id,)
            owner_rows = await self._db_query(query, query_tuple)

            fields = ('agent_identifier', 'start_time')
            owner_data = self._rows_to_dicts(fields, owner_rows)

            owners.append(owner_data)

        # Get the custodians for each record
        custodians = []
        for row in rows:
            record_id = row[0]
            query = ("SELECT agent_identifier, start_time "
                     "FROM record_agent "
                     "INNER JOIN type_enum ON record_agent.agent_type = "
                     "type_enum.id WHERE record_agent.record_id = %s "
                     "AND type_enum.name='CUSTODIAN';")

            query_tuple = (record_id,)
            custodian_rows = await self._db_query(query, query_tuple)

            fields = ('agent_identifier', 'start_time')
            custodian_data = self._rows_to_dicts(fields, custodian_rows)

            custodians.append(custodian_data)

        main_data = [{
            'identifier': rec['identifier'],
            'final': rec['finalize'],
            'creation_time': rec['creation_time'],
        } for rec in rows]

        # Insert the owner and custodian data
        for i, d in enumerate(main_data):
            d['owners'] = owners[i]
            d['custodians'] = custodians[i]

        # Retrieve the max index possible for paging
        count_query = SqlBuilder(
            'SELECT COUNT(*) FROM record ',
            base_where_clause).build()
        return await self._generate_paginated_response(
            request,
            count_query, base_query_variables,
            page_num, count, head, main_data)

    async def fetch_record(self, request):
        """Fetches a specific record, by record_id.

        Request:
            query:
                - record_id: the identifier of the agent to fetch.
                - head: the block_num to use as head for the purpose of
                        retrieving Records

        Response:
            data: JSON response with the record data.
        """

        # Query parameters
        record_id = request.match_info.get('record_id', '')
        head = await self._get_block_num_for_request(request)

        query = ('SELECT id, identifier, creation_time, finalize '
                 'FROM record '
                 'WHERE  %s >= start_block_num AND '
                 '%s <= end_block_num '
                 'AND identifier = %s')

        query_variables = (head, head, record_id)

        rows = await self._db_query(query, query_variables)

        # Only one record should be returned
        if len(rows) > 1:
            LOGGER.exception("Too many rows returned in query.")
            raise errors.UnknownDatabaseError

        elif len(rows) == 1:

            record_id = rows[0]['id']
            # Return the data
            data = {
                'identifier': rows[0][0],
                'creation_time': rows[0][1],
                'final': rows[0][2],
            }

            query_variables = (record_id,)

            # Get the owners for the record
            query = ("SELECT agent_identifier, start_time "
                     "FROM record_agent INNER JOIN type_enum "
                     "ON record_agent.agent_type = type_enum.id "
                     "WHERE record_agent.record_id = %s "
                     "AND type_enum.name='OWNER';")

            owner_rows = await self._db_query(query, query_variables)

            fields = ('agent_identifier', 'start_time')
            owner_data = self._rows_to_dicts(fields, owner_rows)

            # Get the custodians for the record
            query = ("SELECT agent_identifier, start_time "
                     "FROM record_agent INNER JOIN type_enum "
                     "ON record_agent.agent_type = type_enum.id "
                     "WHERE record_agent.record_id = %s "
                     "AND type_enum.name='CUSTODIAN';")

            custodian_rows = await self._db_query(query, query_variables)

            fields = ('agent_identifier', 'start_time')
            custodian_data = self._rows_to_dicts(fields, custodian_rows)

            # Insert the owner and custodian data, remove id field
            data['owners'] = owner_data
            data['custodians'] = custodian_data

            return self._wrap_response(
                request,
                data=data,
                metadata={'head': head})

        else:
            raise errors.RecordNotFound()

    async def fetch_record_applications(self, request):
        """Fetches a paginated list of Applications for a record. Applications
        are identified by the identifier of the Record they are associated
        with. Using the applicant parameter will narrow the list to any
        Applications that may have a matching value their applicant field.
        Using the status parameter narrows the list to any Applications that
        have a matching value in their status field.

        Request:
            match:
                - record_id (required): the record identifier, serial number
                    of natural identifier of the item being tracked.
            query:
                - applicant: the public key of the applicant Agent to filter by
                - status: An application status to filter by
                - count: Number of items to return
                - page: page number, relative to the count
                - head: the block_num to use as head for the purpose of
                        retrieving Agents

        Response:
            data: JSON response with Record's data
            paging: paging info and nav (e.g. next link )
        """

        record_id = request.match_info.get('record_id', '')
        # Get query parameters
        applicant = request.url.query.get('applicant', None)
        status = request.url.query.get('status', None)

        count, page_num = RouteHandler._extract_paging_params(request)
        head = await self._get_block_num_for_request(request)

        # Create query
        base_where_clause = SqlBuilder(
            'WHERE %s >= a.start_block_num '
            'AND %s <= a.end_block_num '
            'AND r.identifier = a.record_identifier '
            'AND a.type = t.id AND a.status = s.id '
            'AND r.identifier = %s ')

        base_query_variables = (head, head, record_id)

        if applicant is not None:
            base_where_clause.add('AND a.applicant = %s')
            base_query_variables += (applicant,)
        if status is not None:
            base_where_clause.add('AND s.name = %s')
            base_query_variables += (status.upper(),)

        query = SqlBuilder(
            'SELECT r.identifier, a.applicant, '
            't.name, s.name, a.terms '
            'FROM record r, application a, '
            'type_enum t, status_enum s ',
            base_where_clause,
            'LIMIT %s OFFSET %s').build()
        query_variables = base_query_variables + (count, page_num)

        rows = await self._db_query(query, query_variables)

        fields = ('identifier', 'applicant', 'type', 'status', 'terms')
        data = self._rows_to_dicts(fields, rows)

        count_query = SqlBuilder(
            "SELECT COUNT(a.*) "
            "FROM record r, application a, "
            "type_enum t, status_enum s ",
            base_where_clause).build()
        return await self._generate_paginated_response(
            request,
            count_query, base_query_variables,
            page_num, count, head, data)

    @staticmethod
    def _rows_to_dicts(fields, rows):
        """
        Convert returned data in the form of lists from DB to dicts,
        and insert the fields as keys. Also trims the type and
        status columns, which may be returned from the database with
        extra whitespace.

        Args:
            fields: the keys use for each column
            rows: the list of records
        Returns: a list of dicts
        """
        def _cond_strip(field, val):
            if field == 'type' or field == 'status':
                return val.strip()
            return val

        return [{f: _cond_strip(f, row[i]) for i, f in enumerate(fields)}
                for row in rows]

    async def _get_block_num_for_request(self, request):
        """Returns the current head block as stored by the block table.

        Args:
            request (obj:`HttpRequest`): the aiohttp request object

        Returns:
            int: block number, either from the request, or, if none, the
                current block_num in the database.
        """
        head = request.url.query.get('head', None)
        if head is None:
            query = ("SELECT max(block_num) FROM block")
            rows = await self._db_query(query)
            return rows[0][0]

        return head

    @staticmethod
    def add_cors_headers(request, headers):
        if 'Origin' in request.headers:
            headers['Access-Control-Allow-Origin'] = request.headers['Origin']
            headers["Access-Control-Allow-Methods"] = "GET,POST"
            headers["Access-Control-Allow-Headers"] =\
                "Origin, X-Requested-With, Content-Type, Accept"

    @staticmethod
    def _extract_paging_params(request):
        """Extracts the paging parmaters from a given request.

        Args:
            request (obj:`HttpRequest`): the aiohttp request object

        Returns:
            (tuple:int,int):
                count: the number of records to return
                page_num: the page number
        """
        count = request.url.query.get('count', DEFAULT_PAGE_SIZE)
        page_num = request.url.query.get('page', 0)

        return RouteHandler._check_paging_params(count, page_num)

    @staticmethod
    def _check_paging_params(count, page_num):
        """Transforms paging parameters into integers and
        checks to make sure that they are not out of range.

        Args:
            count (str): the number of records to return
            page_num (str): the page number

        Returns:
            (tuple:int,int):
                count: the number of records to return
                page_num: the page number
        """
        try:
            count = int(count)
            page_num = int(page_num)
        except ValueError:
            LOGGER.debug("Non-integer paging parameter.")
            raise errors.InvalidPagingQuery()

        if count > DEFAULT_PAGE_SIZE:
            count = DEFAULT_PAGE_SIZE

        if not (count >= 0 and page_num >= 0):
            LOGGER.debug("Invalid paging parameter.")
            raise errors.InvalidPagingQuery()

        return count, page_num

    @staticmethod
    def _wrap_response(request, data=None, metadata=None, status=200):
        """Creates the JSON response envelope to be sent back to the client.
        """
        envelope = metadata or {}

        if data is not None:
            envelope['data'] = data

        headers = {}
        RouteHandler.add_cors_headers(request, headers)

        return web.Response(
            status=status,
            content_type='application/json',
            headers=headers,
            text=json.dumps(
                envelope,
                indent=2,
                separators=(',', ': '),
                sort_keys=True))

    async def _generate_paginated_response(
            self, request, count_query, count_variables,
            page_num, count, head, data):
        rows = await self._db_query(count_query, count_variables)
        (total_count,) = rows[0]

        num_records = len(data)

        paging = {'total_count': total_count}

        # Build paging urls
        next_page = page_num + 1
        if num_records > 0 and (next_page * count) <= total_count:
            paging['next'] = RouteHandler._build_url(
                request, count=count, page=next_page, head=head)

        # paging = paging_info
        metadata = {'paging': paging, 'head': head}
        return RouteHandler._wrap_response(
            request,
            data=data,
            metadata=metadata
        )

    @classmethod
    def _build_url(cls, request, path=None, **changes):
        """Builds a response URL by overriding the original queries with
        specified change queries. Change queries set to None will not be used.
        Setting a change query to False will remove it even if there is an
        original query with a value.
        """
        changes = {k: v for k, v in changes.items() if v is not None}
        queries = {**request.url.query, **changes}
        queries = {k: v for k, v in queries.items() if v is not False}
        query_strings = []

        def add_query(key):
            query_strings.append('{}={}'.format(key, queries[key])
                                 if queries[key] != '' else key)

        def del_query(key):
            queries.pop(key, None)

        if 'page' in changes:
            add_query('page')
        elif 'page' in queries:
            add_query('page')

        del_query('page')

        if 'count' in queries:
            add_query('count')
            del_query('count')

        for key in sorted(queries):
            add_query(key)

        scheme = cls._get_forwarded(request, 'proto') or request.url.scheme
        host = cls._get_forwarded(request, 'host') or request.host
        forwarded_path = cls._get_forwarded(request, 'path')
        path = path if path is not None else request.path
        query = '?' + '&'.join(query_strings) if query_strings else ''

        url = '{}://{}{}{}{}'.format(scheme, host, forwarded_path, path, query)
        return url

    @staticmethod
    def _get_forwarded(request, key):
        """Gets a forwarded value from the `Forwarded` header if present, or
        the equivalent `X-Forwarded-` header if not. If neither is present,
        returns an empty string.
        """
        forwarded = request.headers.get('Forwarded', '')
        match = re.search(
            r'(?<={}=).+?(?=[\s,;]|$)'.format(key),
            forwarded,
            re.IGNORECASE)

        if match is not None:
            header = match.group(0)

            if header[0] == '"' and header[-1] == '"':
                return header[1:-1]

            return header

        return request.headers.get('X-Forwarded-{}'.format(key.title()), '')

    @staticmethod
    def _remove_id_field(data):
        for row in data:
            row.pop('id', None)
        return data

    async def _db_query(self, query, query_variables=()):
        """Performs asynchronous query on PostgreSQL database, using
        the query string and the query variables to insert into the
        query string.

        Args:
            query (str): Query to execute
            query_variables (tuple): Query variables to insert into query

        Returns:
            list: A list of rows. Each row is a list of columns/fields.

        """
        pool = None
        conn = None
        cur = None
        try:
            pool = await aiopg.create_pool(
                dbname=self._config.database_name,
                host=self._config.database_host,
                port=self._config.database_port,
                user=self._config.database_user,
                password=self._config.database_password)

            conn = await pool.acquire()
            cur = await conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            # Execute the query
            try:
                await cur.execute(query, query_variables)
            except psycopg2.DatabaseError:
                LOGGER.exception("Could not execute query: %s", query)
                raise errors.UnknownDatabaseError()

            # Fetch the rows
            return [row for row in cur]

        except psycopg2.OperationalError:
            LOGGER.exception("Could not connect to database.")
            raise errors.DatabaseConnectionError
        finally:
            if cur:
                cur.close()
            if pool and conn:
                pool.release(conn)
