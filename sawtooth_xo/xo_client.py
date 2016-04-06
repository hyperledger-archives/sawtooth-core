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

import logging
import time

from twisted.web import http

from gossip import node, signed_object
from sawtooth_xo.xo_communication import XoCommunication
from sawtooth_xo.xo_communication import MessageException
from sawtooth_xo.xo_state import XoState
from sawtooth_xo.txn_family import XoTransaction
from sawtooth_xo.txn_family import XoTransactionMessage
from sawtooth_xo.txn_family import XoUpdate

logger = logging.getLogger(__name__)


class XoClient(XoCommunication):
    def __init__(self,
                 baseurl,
                 name='XoClient',
                 keystring=None,
                 keyfile=None,
                 state=None):
        super(XoClient, self).__init__(baseurl)
        self.LastTransaction = None

        self.CurrentState = state or XoState(self.BaseURL)
        self.CurrentState.fetch()

        # set up the signing key
        if keystring:
            logger.debug("set signing key from string\n%s", keystring)
            signingkey = signed_object.generate_signing_key(wifstr=keystring)
        elif keyfile:
            logger.debug("set signing key from file %s", keyfile)
            signingkey = signed_object.generate_signing_key(
                wifstr=open(keyfile, "r").read().strip())
        else:
            raise TypeError('expecting valid signing key, none provided')

        identifier = signed_object.generate_identifier(signingkey)
        self.LocalNode = node.Node(identifier=identifier,
                                   signingkey=signingkey,
                                   name=name)

    def _sendtxn(self, update):
        """
        Build a transaction for the update, wrap it in a message with all
        of the appropriate signatures and post it to the validator
        """

        txn = XoTransaction()
        txn.Updates = [update]

        # add the last transaction submitted to ensure that the ordering
        # in the journal matches the order in which we generated them
        if self.LastTransaction:
            txn.Dependencies = [self.LastTransaction]

        update.Transaction = txn
        txn.sign_from_node(self.LocalNode)
        txnid = txn.Identifier

        if not txn.is_valid(self.CurrentState.State):
            logger.warn('transaction failed to apply')
            return None

        msg = XoTransactionMessage()
        msg.Transaction = txn
        msg.SenderID = self.LocalNode.Identifier
        msg.sign_from_node(self.LocalNode)

        try:
            logger.debug('Posting transaction: %s', txnid)
            result = self.postmsg(msg.MessageType, msg.dump())

        except MessageException as me:
            return None

        except:
            logger.debug('message post failed for some unusual reason')
            return None

        # if there was no exception thrown then all transactions should return
        # a value which is a dictionary with the message that was sent
        assert result

        # if the message was successfully posted, then save the transaction
        # id for future dependencies this could be a problem if the transaction
        # fails during application
        self.LastTransaction = txnid
        txn.apply(self.CurrentState.State)

        return txnid

    def waitforcommit(self, txnid=None, timetowait=5, iterations=12):
        """
        Wait until a specified transaction shows up in the ledger's committed
        transaction list

        :param id txnid: the transaction to wait for, the last transaction by
            default
        :param int timetowait: time to wait between polling the ledger
        :param int iterations: number of iterations to wait before giving up
        """

        if not txnid:
            txnid = self.LastTransaction
        if not txnid:
            logger.info('no transaction specified for wait')
            return True

        passes = 0
        while True:
            passes += 1
            status = self.headrequest('/transaction/{0}'.format(txnid))

            if status == http.NOT_FOUND and passes > iterations:
                logger.warn('unknown transaction %s', txnid)
                return False

            if status == http.OK:
                return True

            logger.debug('waiting for transaction %s to commit', txnid)
            time.sleep(timetowait)

    def set(self, key, value):
        """
        """
        update = XoUpdate({
            "Verb": "set",
            "Name": key,
            "Value": value
        })

        return self._sendtxn(update)

    def inc(self, key, value):
        """
        """
        update = XoUpdate({
            "Verb": "inc",
            "Name": key,
            "Value": value
        })

        return self._sendtxn(update)

    def dec(self, key, value):
        """
        """
        update = XoUpdate({
            "Verb": "dec",
            "Name": key,
            "Value": value
        })

        return self._sendtxn(update)
