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

# Supply Chain REST API

import logging
import json
from concurrent.futures import ThreadPoolExecutor
import psycopg2
import aiopg
from aiohttp import web

import sawtooth_supplychain.rest_api.exceptions as errors


DEFAULT_TIMEOUT = 300
LOGGER = logging.getLogger(__name__)
DEFAULT_PAGE_SIZE = 1000    # Reasonable default


async def db_query(db_cnx, query, query_tuple):
    try:
        async with aiopg.create_pool(db_cnx) as pool:
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    # Execute the query
                    try:
                        await cur.execute(query, query_tuple)
                    except:
                        LOGGER.debug("Could not execute query: %s", query)
                        raise errors.UnknownDatabaseError()

                    # Fetch the rows
                    rows = []
                    async for row in cur:
                        rows.append(row)
                    return rows

    except psycopg2.OperationalError as e:
        raise e


class RouteHandler(object):
    """Contains a number of aiohttp handlers for endpoints in
    the Supply Chain Rest Api.

    Each handler takes an aiohttp Request object, and uses the data in
    that request to create queries to send to the database. The query
    results are processed, and finally an aiohttp Response object is
    sent back to the client with JSON formatted data and metadata.

    If something goes wrong, an aiohttp HTTP exception is raised or returned
    instead.

    Args:
        stream (:obj: messaging.stream.Stream):
        timeout (int, optional): The time in seconds before the Api should
            cancel a request and report that the validator is unavailable.
    """
    def __init__(self, loop, db_cnx=None):
        loop.set_default_executor(ThreadPoolExecutor())
        self._loop = loop
        self._db_cnx = db_cnx

    async def list_agents(self, request):
        """Fetches a paginated list of all Agents. Using the name filter
        parameter narrows the list to any Agents who have a name which
        contains a specified case-insensitive string.

        Request:
            query:
                - name: a partial name to filter Agents by
                - count: Number of items to return
                - min: Id or index to start paging (inclusive)
                - max: Id or index to end paging (inclusive)

        Response:
            data: JSON array of Agents
        """

        # Get query parameters
        name = request.url.query.get('name', '')
        count = request.url.query.get('count', DEFAULT_PAGE_SIZE)
        p_min = request.url.query.get('min', 0)
        p_max = request.url.query.get('max', None)

        count, p_min, p_max = \
            RouteHandler._check_paging_params(count, p_min, p_max)

        # Create query
        name = "%" + name + "%"  # Add pattern matching to search string
        query_tuple = ()


        if p_max is not None:
            query = ("SELECT identifier, name FROM agent WHERE name like %s "
                     "AND id >= %s AND id <= %s ORDER BY id limit %s")
            query_tuple += (name, p_min, p_max, count)
        else:
            query = ("SELECT identifier, name FROM agent WHERE name like %s "
                     "AND id >= %s ORDER BY id limit %s")
            query_tuple += (name, p_min, count)

        try:
            # async with aiopg.create_pool(self._db_cnx) as pool:
            #     async with pool.acquire() as conn:
            #         async with conn.cursor() as cur:
            #
            #             # Execute the query
            #             try:
            #                 await cur.execute(query, query_tuple)
            #             except:
            #                 LOGGER.debug("Could not execute query: %s", query)
            #                 raise errors.UnknownDatabaseError()
            #
            #             # Fetch the rows
            #             rows = []
            #             async for row in cur:
            #                 rows.append(row)

            rows = await db_query(self._db_cnx, query, query_tuple)

        except psycopg2.OperationalError as e:
            LOGGER.debug("Could not connect to database.")
            raise errors.DatabaseConnectionError

        fields = ('identifier', 'name')
        data = self._make_dict(fields, rows)

        response = self._wrap_response(
            request,
            data=data,
            metadata="")

        return response

    async def fetch_agent(self, request):
        """Fetches a specific agent, by identifier.

        Request:
            query:
                - agent_id: the identifier of the agent to fetch

        Response:
            data: JSON response with Agent data
        """

        agent_id = request.match_info.get('agent_id', '')

        # Create query
        query = "select identifier, name from agent where identifier = %s;"
        query_tuple = (agent_id,)

        try:
            # async with aiopg.create_pool(self._db_cnx) as pool:
            #     async with pool.acquire() as conn:
            #         async with conn.cursor() as cur:
            #
            #             # Execute the query
            #             try:
            #                 await cur.execute(query, query_tuple)
            #             except:
            #                 LOGGER.debug("Could not execute query: %s", query)
            #                 raise errors.UnknownDatabaseError()
            #
            #             # Fetch the rows
            #             rows = []
            #             async for row in cur:
            #                 rows.append(row)
            rows = await db_query(self._db_cnx, query, query_tuple)
        except psycopg2.OperationalError as e:
            LOGGER.debug("Could not connect to database.")
            raise errors.DatabaseConnectionError

        if len(rows) > 1:
            LOGGER.debug("Too many rows returned.")
            errors.UnknownDatabaseError()

        elif len(rows) == 1:
            # Return the data
            fields = ('identifier', 'name')
            data = self._make_dict(fields, rows).pop()

            return self._wrap_response(
                request,
                data=data,
                metadata="")

        else:
            raise errors.AgentNotFound()

    async def list_applications(self, request):
        """Fetches the data for the current set of Applications

        Request:
            query:
                - applicant: the public key of the applicant Agent to filter by
                - status: An application status to filter by
                - count: Number of items to return
                - min: Id or index to start paging (inclusive)
                - max: Id or index to end paging (inclusive)

        Response:
            data: JSON response with array of Applications
            paging: paging info and nav (e.g. next link )
        """

        # Get query parameters
        applicant = request.url.query.get('applicant', None)
        status = request.url.query.get('status', None)
        count = request.url.query.get('count', DEFAULT_PAGE_SIZE)
        p_min = request.url.query.get('min', 0)
        p_max = request.url.query.get('max', None)

        count, p_min, p_max = \
            RouteHandler._check_paging_params(count, p_min, p_max)

        # Create query
        query = ("SELECT application.record_identifier, application.applicant,"
                 " type_enum.name, status_enum.name, application.terms "
                 "FROM application, type_enum, status_enum "
                 "WHERE application.type = type_enum.id "
                 "AND application.status = status_enum.id")

        query_tuple = ()

        if applicant is not None:
            query += " AND application.applicant = %s"
            query_tuple += (applicant,)

        if status is not None:
            query += " AND status_enum.name = %s"
            query_tuple += (status,)

        if p_max is not None:
            query += (" AND application.id >= %s AND application.id <= %s "
                      "ORDER BY application.id limit %s")
            query_tuple += (p_min, p_max, count)
        else:
            query += (" AND application.id >= %s "
                      "ORDER BY application.id limit %s")
            query_tuple += (p_min, count)

        try:
            # async with aiopg.create_pool(self._db_cnx) as pool:
            #     async with pool.acquire() as conn:
            #         async with conn.cursor() as cur:
            #
            #             # Execute the query
            #             try:
            #                 await cur.execute(query, query_tuple)
            #             except:
            #                 LOGGER.debug("Could not execute query: %s", query)
            #                 raise errors.UnknownDatabaseError()
            #
            #             # Fetch the rows
            #             rows = []
            #             async for row in cur:
            #                 rows.append(row)
            rows = await db_query(self._db_cnx, query, query_tuple)
        except psycopg2.OperationalError as e:
            LOGGER.debug("Could not connect to database.")
            raise errors.DatabaseConnectionError

        # Return the data
        fields = ('identifier', 'applicant', 'type', 'status', 'terms')
        data = self._make_dict(fields, rows)

        return self._wrap_response(
            request,
            data=data,
            metadata="")

    async def list_records(self, request):
        """Fetches the data for the current set of Records

        Request:
            query:
                - identifier: A partial identifier to filter Records by
                - count: Number of itemst to return
                - min: Id or index to start paging (inclusive)
                - max: Id or index to end paging (inclusive)

        Response:
            data: JSON response with array of Records
            paging: paging info and nav (e.g. next link )
        """

        # Get query parameters
        identifier = request.url.query.get('identifier', '')
        count = request.url.query.get('count', DEFAULT_PAGE_SIZE)
        p_min = request.url.query.get('min', 0)
        p_max = request.url.query.get('max', None)

        count, p_min, p_max = \
            RouteHandler._check_paging_params(count, p_min, p_max)

        # Create query
        query = ("SELECT id, identifier, creation_time, finalized "
                 "FROM record WHERE identifier LIKE %s")

        # Add pattern matching to search string
        identifier = "%" + identifier + "%"
        query_tuple = (identifier,)

        if p_max is not None:
            query += " AND id >= %s AND id <= %s ORDER BY id limit %s"
            query_tuple += (p_min, p_max, count)
        else:
            query += " AND id >= %s ORDER BY id limit %s"
            query_tuple += (p_min, count)

        # Get a connection and cursor
        try:
            rows = await db_query(self._db_cnx, query, query_tuple)

            # Get the owners for each record
            owners = []
            for row in rows:
                record_id = row[0]
                query = ("SELECT agent_identifier, start_time FROM record_agent "
                         "INNER JOIN type_enum ON record_agent.agent_type = "
                         "type_enum.id WHERE record_agent.record_id = %s "
                         "AND type_enum.name='OWNER';")

                query_tuple = (record_id,)
                owner_rows = await db_query(self._db_cnx, query, query_tuple)

                fields = ('agent_identifier', 'start_time')
                owner_data = self._make_dict(fields, owner_rows)

                owners.append(owner_data)

            # Get the custodians for each record
            custodians = []
            for row in rows:
                record_id = row[0]
                query = ("SELECT agent_identifier, start_time FROM record_agent "
                         "INNER JOIN type_enum ON record_agent.agent_type = "
                         "type_enum.id WHERE record_agent.record_id = %s "
                         "AND type_enum.name='CUSTODIAN';")

                query_tuple = (record_id,)
                custodian_rows = await db_query(self._db_cnx, query, query_tuple)

                fields = ('agent_identifier', 'start_time')
                custodian_data = self._make_dict(fields, custodian_rows)

                custodians.append(custodian_data)

            fields = ('id', 'identifier', 'creation_time', 'final')
            main_data = self._make_dict(fields, rows)

            # Insert the owner and custodian data, remove id field
            for i, d in enumerate(main_data):
                d['owners'] = owners[i]
                d['custodians'] = custodians[i]
                d.pop('id', None)

            return self._wrap_response(
                request,
                data=main_data,
                metadata="")

        except psycopg2.OperationalError as e:
            LOGGER.debug("Could not connect to database.")
            raise errors.DatabaseConnectionError

    async def fetch_record(self, request):
        """Fetches a specific record, by record_id.

        Request:
            query:
                - record_id: the identifier of the agent to fetch.

        Response:
            data: JSON response with the record data.
        """

        # Query parameters
        record_id = request.match_info.get('record_id', '')

        # Create query
        query = ("SELECT id, identifier, creation_time, finalized "
                 "FROM record WHERE identifier = %s;")

        query_tuple = (record_id,)

        try:
            rows = await db_query(self._db_cnx, query, query_tuple)

            # Only one record should be returned
            if len(rows) > 1:

                LOGGER.debug("Too many rows returned in query.")
                raise errors.UnknownDatabaseError

            elif len(rows) == 1:

                # Return the data
                fields = ('id', 'identifier', 'creation_time', 'final')
                data = self._make_dict(fields, rows)

                # Get the owners for the record
                owners = []
                record_id = data[0]['id']

                query = ("SELECT agent_identifier, start_time "
                         "FROM record_agent INNER JOIN type_enum "
                         "ON record_agent.agent_type = type_enum.id "
                         "WHERE record_agent.record_id = %s "
                         "AND type_enum.name='OWNER';")

                query_tuple = (record_id,)
                owner_rows = await db_query(self._db_cnx, query, query_tuple)

                fields = ('agent_identifier', 'start_time')
                owner_data = self._make_dict(fields, owner_rows)
                owners.append(owner_data)

                #Get the custodians for the record
                custodians = []
                query = ("SELECT agent_identifier, start_time "
                         "FROM record_agent INNER JOIN type_enum "
                         "ON record_agent.agent_type = type_enum.id "
                         "WHERE record_agent.record_id = %s "
                         "AND type_enum.name='CUSTODIAN';")

                query_tuple = (record_id,)
                custodian_rows = await db_query(self._db_cnx, query, query_tuple)

                fields = ('agent_identifier', 'start_time')
                custodian_data = self._make_dict(fields, custodian_rows)

                custodians.append(custodian_data)

                # Insert the owner and custodian data, remove id field
                for i, d in enumerate(data):
                    d['owners'] = owners[i]
                    d['custodians'] = custodians[i]
                    d.pop('id', None)

                return_data = data.pop()

                return self._wrap_response(
                    request,
                    data=return_data,
                    metadata="")

            else:
                raise errors.RecordNotFound()

        except psycopg2.OperationalError as e:
            LOGGER.debug("Could not connect to database.")
            raise errors.DatabaseConnectionError

    async def fetch_applications(self, request):
        """Fetches a paginated list of Applications for a record. Applications
        are identified by the identifier of the Record they are associated
        with. Using the applicant parameter will narrow the list to any
        Applications that may have a matching value their applicant field.
        Using the status parameter narrows the list to any Applications that
        have a matching value in their status field.

        Request:
            query:
                - applicant: the public key of the applicant Agent to filter by
                - status: An application status to filter by
                - count: Number of items to return
                - min: Id or index to start paging (inclusive)
                - max: Id or index to end paging (inclusive)
                - record_id (required): the record identifier, serial number
                    of natural identifier of the item being tracked.

        Response:
            data: JSON response with Record's data
        """

        # Get query parameters
        record_id = request.match_info.get('record_id', '')
        applicant = request.url.query.get('applicant', None)
        status = request.url.query.get('status', None)
        count = request.url.query.get('count', DEFAULT_PAGE_SIZE)
        p_min = request.url.query.get('min', 0)
        p_max = request.url.query.get('max', None)

        count, p_min, p_max = \
            RouteHandler._check_paging_params(count, p_min, p_max)

        # Create query
        query = ("SELECT record.identifier, application.applicant, "
                 "type_enum.name, status_enum.name, application.terms "
                 "FROM record, application, type_enum, status_enum "
                 "WHERE record.identifier = application.record_identifier "
                 "AND application.type = type_enum.id "
                 "AND application.status=status_enum.id "
                 "AND record.identifier = %s")

        query_tuple = (record_id,)

        if applicant is not None:
            query += " AND application.applicant = %s"
            query_tuple += (applicant,)
        if status is not None:
            query += " AND status_enum.name = %s"
            query_tuple += (status,)

        if p_max is not None:
            query += (" AND application.id >= %s "
                      "AND application.id <= %s "
                      "ORDER BY application.id limit %s")
            query_tuple += (p_min, p_max, count)
        else:
            query += (" AND application.id >= %s "
                      "ORDER BY application.id limit %s")
            query_tuple += (p_min, count)

        # Get a connection and cursor
        try:
            rows = await db_query(self._db_cnx, query, query_tuple)

        except psycopg2.OperationalError as e:
            LOGGER.debug("Could not connect to database.")
            raise errors.DatabaseConnectionError

        fields = ('identifier', 'applicant', 'type', 'status', 'terms')
        data = self._make_dict(fields, rows)

        return self._wrap_response(
            request,
            data=data,
            metadata=""
        )

    @staticmethod
    def _make_dict(fields, rows):
        """
        Convert returned data in the form of lists from DB to dicts,
        and insert the fields as keys.
        """

        data = []

        for row in rows:
            record = {}
            for i, f in enumerate(fields):
                if f in ['type', 'status']:
                    record[f] = row[i].strip()
                else:
                    record[f] = row[i]
            data.append(record)
        return data

    @staticmethod
    def add_cors_headers(request, headers):
        if 'Origin' in request.headers:
            headers['Access-Control-Allow-Origin'] = request.headers['Origin']
            headers["Access-Control-Allow-Methods"] = "GET,POST"
            headers["Access-Control-Allow-Headers"] =\
                "Origin, X-Requested-With, Content-Type, Accept"

    @staticmethod
    def _check_paging_params(count, p_min, p_max):
        """Check paging params to make sure they are integers and
        that they are not out of range.
        """
        try:
            count = int(count)
            p_min = int(p_min)
            if p_max is not None:
                p_max = int(p_max)
        except:
            LOGGER.debug("Non-integer paging parameter.")
            raise errors.InvalidPagingQuery()

        if int(count) > DEFAULT_PAGE_SIZE:
            LOGGER.debug("Count parameter is greater than DEFAULT_PAGE_SIZE.")
            raise errors.CountInvalid()

        if not (count >= 0 and p_min >= 0):
            LOGGER.debug("Invalid paging parameter.")
            raise errors.InvalidPagingQuery()

        if p_max is not None:
            if p_max < 0:
                LOGGER.debug("Invalid paging parameter.")
                raise errors.InvalidPagingQuery()

        return count, p_min, p_max

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
