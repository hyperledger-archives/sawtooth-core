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
import sys
import logging

import psycopg2

from sawtooth_supplychain.subscriber.config import SubscriberConfig
from sawtooth_supplychain.subscriber.config import load_subscriber_config


LOGGER = logging.getLogger(__name__)


CREATE_BLOCK_STMTS = """
CREATE TABLE IF NOT EXISTS block (
    block_id         char(128) primary key,
    block_num        integer,
    state_root_hash  char(64)
);

CREATE INDEX IF NOT EXISTS block_num_idx
ON block (block_num);
"""

CREATE_RECORD_STMTS = """
CREATE TABLE IF NOT EXISTS record (
    id                  bigserial primary key,
    start_block_num     integer,
    end_block_num       integer,
    identifier          varchar(128),
    creation_time       bigint,
    finalize            boolean
);

CREATE INDEX IF NOT EXISTS record_identifier_block_num_idx
  ON record (identifier, end_block_num NULLS FIRST);
"""

CREATE_AGENT_STMTS = """
CREATE TABLE IF NOT EXISTS agent(
    id               bigserial primary key,
    start_block_num  integer,
    end_block_num    integer,
    identifier       varchar(128),
    name             text
);

CREATE INDEX IF NOT EXISTS agent_identifier_block_num_idx
  ON agent (identifier, end_block_num NULLS FIRST);
"""

CREATE_TYPE_ENUM_STMTS = """
CREATE TABLE IF NOT EXISTS type_enum(
    id    integer primary key,
    name  char(12),
    code  smallint
);
INSERT INTO type_enum
VALUES (0, 'OWNER', 0),
       (1, 'CUSTODIAN', 1)
 ON CONFLICT DO NOTHING;
"""

CREATE_STATUS_ENUM_STMTS = """
CREATE TABLE IF NOT EXISTS status_enum(
    id    integer primary key,
    name  char(12),
    code  smallint
);

INSERT INTO status_enum
VALUES (0, 'OPEN', 0),
       (1, 'CANCELED', 1),
       (2, 'REJECTED', 2),
       (3, 'ACCEPTED', 3)
 ON CONFLICT DO NOTHING;
"""

CREATE_RECORD_AGENT_STMTS = """
CREATE TABLE IF NOT EXISTS record_agent(
    id                bigserial primary key,
    record_id         bigserial references record(id),
    agent_identifier  varchar(128),
    start_time        bigint,
    agent_type        integer  references type_enum(id)
);

"""

CREATE_APPLICATION_STMTS = """
CREATE TABLE IF NOT EXISTS application(
    id                 bigserial primary key,
    start_block_num    integer,
    end_block_num      integer,
    record_identifier  varchar(128),
    applicant          varchar(128),
    creation_time      bigint,
    type               integer references type_enum(id),
    status             integer references status_enum(id),
    terms              text
);

CREATE INDEX IF NOT EXISTS application_record_id_block_num_idx
  ON application (record_identifier, end_block_num NULLS FIRST);
"""


def do_init(opts):
    opts_config = SubscriberConfig(
        database_name=opts.database_name,
        database_host=opts.database_host,
        database_port=opts.database_port,
        database_user=opts.database_user,
        database_password=opts.database_password)
    subscriber_config = load_subscriber_config(opts_config)

    connection = None
    # pylint: disable=broad-except
    try:
        connection = psycopg2.connect(
            dbname=subscriber_config.database_name,
            host=subscriber_config.database_host,
            port=subscriber_config.database_port,
            user=subscriber_config.database_user,
            password=subscriber_config.database_password)

        with connection.cursor() as cursor:
            cursor.execute(CREATE_BLOCK_STMTS)
            cursor.execute(CREATE_RECORD_STMTS)
            cursor.execute(CREATE_AGENT_STMTS)
            cursor.execute(CREATE_TYPE_ENUM_STMTS)
            cursor.execute(CREATE_STATUS_ENUM_STMTS)
            cursor.execute(CREATE_RECORD_AGENT_STMTS)
            cursor.execute(CREATE_APPLICATION_STMTS)

        connection.commit()

    except Exception as e:
        print('Unable to initialize subscriber database: {}'.format(str(e)),
              file=sys.stderr)
    finally:
        if connection is not None:
            connection.close()
