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

import copy
import logging
import traceback

from zope.interface import Interface, Attribute, implements
from twisted.python.components import registerAdapter
from twisted.web import http
from twisted.web.error import Error
from twisted.web.server import Session

from sawtooth.exceptions import InvalidTransactionError
from txnserver.web_pages.base_page import BasePage


LOGGER = logging.getLogger(__name__)


# pylint: disable=inherit-non-class
class ITempTransactionTypeStore(Interface):
    count = Attribute("An int value")
    my_store = Attribute("A store value")


class TempTransactionTypeStoreInstance(object):
    implements(ITempTransactionTypeStore)

    def __init__(self, session):
        self.count = 0
        self.my_store = None


registerAdapter(TempTransactionTypeStoreInstance, Session,
                ITempTransactionTypeStore)


class PrevalidationPage(BasePage):
    isLeaf = True

    def __init__(self, validator, page_name=None):
        BasePage.__init__(self, validator, page_name)

    def render_get(self, request, components, msg):
        session = request.getSession()
        if request.method == 'HEAD':
            if not session:
                raise \
                    Error(http.BAD_REQUEST, 'Session has not been started')

            session.expire()
            LOGGER.info('Session: %s has ended.', session.uid)
            return 'Session: {} has ended.'.format(session.uid)

        temp_store_session = ITempTransactionTypeStore(session)
        return temp_store_session.my_store.dump(True)

    def render_post(self, request, components, msg):
        """
        Do server-side session prevalidation.
        """
        session = request.getSession()
        if not session:
            raise \
                Error(http.BAD_REQUEST, 'Session has not been started')

        data = request.content.getvalue()
        msg = self._get_message(request)

        # if it is an error response message, returns it immediately
        if isinstance(msg, dict) and 'status' in msg:
            return msg

        mymsg = copy.deepcopy(msg)

        if hasattr(mymsg, 'Transaction') and mymsg.Transaction is not None:
            mytxn = mymsg.Transaction
            LOGGER.info('starting server-side prevalidation '
                        'for txn id: %s type: %s',
                        mytxn.Identifier,
                        mytxn.TransactionTypeName)

            transaction_type = mytxn.TransactionTypeName

            temp_store_session = ITempTransactionTypeStore(session)
            temp_store_session.count += 1
            LOGGER.debug('visit %d times in the session.uid: %s',
                         temp_store_session.count, session.uid)

            if not temp_store_session.my_store:
                temp_store_map = self._get_store_map()
                if transaction_type not in temp_store_map.transaction_store:
                    LOGGER.info('transaction type %s not in global store map',
                                transaction_type)
                    raise Error(http.BAD_REQUEST,
                                'unable to prevalidate enclosed '
                                'transaction {0}'.format(data))

                tstore = temp_store_map.get_transaction_store(transaction_type)
                temp_store_session.my_store = tstore.clone_store()

            try:
                if not mytxn.is_valid(temp_store_session.my_store):
                    raise InvalidTransactionError('invalid transaction')

            except InvalidTransactionError as e:
                LOGGER.info('submitted transaction fails transaction '
                            'family validation check: %s; %s',
                            request.path, mymsg.dump())
                raise Error(http.BAD_REQUEST,
                            'InvalidTransactionError: failed transaction '
                            'family validation check: {}'.format(str(e)))
            except:
                LOGGER.info('submitted transaction is '
                            'not valid %s; %s; %s',
                            request.path, mymsg.dump(),
                            traceback.format_exc(20))
                raise Error(http.BAD_REQUEST,
                            'enclosed transaction is not '
                            'valid {}'.format(data))

            LOGGER.info('transaction %s is valid',
                        msg.Transaction.Identifier)
            mytxn.apply(temp_store_session.my_store)

        return msg
