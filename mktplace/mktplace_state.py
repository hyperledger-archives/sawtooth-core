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
"""
Wrapper for the market place state
"""

import logging

from mktplace.mktplace_communication import MarketPlaceCommunication
from mktplace.transactions.market_place import MarketPlaceGlobalStore

logger = logging.getLogger(__name__)


class Filters(object):
    """
    A class that wraps a number of useful lambda expressions that
    can be used for the lambdafilter function on MarketPlaceState
    collections.
    """

    @staticmethod
    def _reference(objid, field):
        return objinfo.get('asset')

    @staticmethod
    def matchvalue(field, value):
        """
        Predicate: match objects that have the given field and the
        value for the field matches the given value
        """
        return lambda objinfo: objinfo.get(field) == value

    @staticmethod
    def references(field, idlist):
        """
        Predicte: match objects that have the given field and the
        value for the field references one of the objects in the list
        """
        return lambda objinfo: objinfo.get(field) in idlist

    @staticmethod
    def matchtype(objtype):
        """
        Predicate: match objects with the given type
        """
        return lambda objinfo: objinfo.get('object-type') == objtype

    @staticmethod
    def offers():
        """
        Predicate: match objects with either ExchangeOffer or SellOffer type
        """
        return lambda objinfo: objinfo.get('object-type') in [
            'ExchangeOffer', 'SellOffer']

    @staticmethod
    def holdings():
        """
        Predicate: match objects with either Holding or Liability type
        """
        return lambda objinfo: objinfo.get('object-type') in [
            'Holding', 'Liability']


class MarketPlaceState(MarketPlaceCommunication):
    """
    A class to wrap the current ledger state for a market place. Retrieves
    the state from a validator and builds maps for names and ids. Exports
    methods for querying state.

    :param url baseurl: the base URL for a Sawtooth Lake validator that
        supports an HTTP interface
    :param id creator: the identifier for the participant generating
        transactions

    :var dict State: The key/value store associated with the head of the
        ledger, for the MarketPlace store, keys are object identifiers and the
        values are the current state of each object.

    """

    def __init__(self, baseurl, creator=None, creator_name=None):
        super(MarketPlaceState, self).__init__(baseurl)

        self._state = None
        self.State = None
        self.ScratchState = None
        self.CurrentBlockID = None

        self.fetch()

        self.CreatorID = creator
        if not self.CreatorID and creator_name:
            self.CreatorID = self.State.n2i('//' + creator_name)

    def bind(self, name, objectid):
        """
        Add a binding between a fully qualified name and an objectid

        :param str name: fully qualified object name
        :param id objectid: object identifier
        """

        return self.State.bind(name, objectid)

    def unbind(self, name):
        """
        Drop the binding of a name to an identifier

        :param str name: object name
        """
        return self.State.unbind(name)

    def n2i(self, name):
        """
        Convert a name into an identifier. The name can take one of these
        forms:
            @ -- resolves to the identifier for creator
            ///<IDENTIFIER>  -- resolves to the identifier
            //<CREATOR>/<PATH> -- fully qualified name
            /<PATH> -- resolve relative to the current creator if specified

        :param str name: object name
        :return: object identifier
        :rtype: id
        """
        if name == '@':
            return self.CreatorID

        if not name.startswith('//'):
            cname = self.i2n(self.CreatorID)
            if not cname:
                return None
            name = '{0}{1}'.format(cname, name)

        return self.State.n2i(name)

    def i2n(self, objectid):
        """
        Construct the fully qualified name for an object

        If the object does not have a name the format will be ///<IDENTIFIER>
        If the object is a participant the format will be //<NAME>
        Otherwise the format will be //<CREATOR NAME>/<NAME>

        :param id objectid: identifier for the object
        :return: the fully qualified name for the object
        :rtype: str
        """
        return self.State.i2n(objectid)

    def fetch(self, store='MarketPlaceTransaction'):
        """
        Retrieve the current state from the validator. Rebuild
        the name, type, and id maps for the resulting objects.

        :param str store: optional, the name of the marketplace store to
            retrieve
        """

        logger.debug('fetch state from %s/%s/*', self.BaseURL, store)

        blockids = self.getmsg('/block?blockcount=10')
        blockid = blockids[0]

        if blockid == self.CurrentBlockID:
            return

        if self.CurrentBlockID in blockids:
            fetchlist = blockids[:blockids.index(self.CurrentBlockID)]
            for fetchid in reversed(fetchlist):
                logger.debug('only fetch delta of state for block %s', fetchid)
                delta = self.getmsg(
                    '/store/{0}/*?delta=1&blockid={1}'.format(store, fetchid))
                self._state = self._state.clone_store(delta)
        else:
            logger.debug('full fetch of state for block %s', blockid)
            state = self.getmsg(
                "/store/{0}/*?blockid={1}".format(store, blockid))
            self._state = MarketPlaceGlobalStore(prevstore=None,
                                                 storeinfo={'Store': state,
                                                            'DeletedKeys': []})

        # State is actually a clone of the block state, this is a free
        # operation because of the copy on write implementation of the global
        #  store. This way market clients can update the state speculatively
        # without corrupting the synchronized storage
        self.State = self._state.clone_store()
        self.CurrentBlockID = blockid

    def path(self, path):
        """
        Function to retrieve the value of a property of an object in the
        saved state

        Args:
            path -- '.' separate expression for extracting a value from state
        """

        pathargs = path.split('.')
        value = self.State
        while pathargs:
            value = value.get(pathargs.pop(0))

        return value

    def lambdafilter(self, *predicates):
        """
        Apply a series of predicates to state objects. Predicates are
        lambda expressions on the data of an object. See the Filters class
        for tools for creating lambda expressions.

        :param predicates: a list of predicates used to filter the set of
            objects
        :type predicates: list of lambda functions
        :returns: a list of object identifiers
        :rtype: list of identifiers
        """

        objlist = []
        for objid, objinfo in self.State.iteritems():
            match = True
            for predicate in predicates:
                if not predicate(objinfo):
                    match = False
                    break

            if match:
                objlist.append(objid)

        return objlist

    def list(self, objtype=None, creator=None, name=None, fields=None):
        """
        Simple filter for common query operations on the current state
        """
        result = []
        for objid, objinfo in self.State.iteritems():
            if objtype and objinfo.get('object-type') != objtype:
                continue

            if creator and objinfo.get('creator') != creator:
                continue

            if name and not objinfo.get('name').startswith(name):
                continue

            # provide a couple useful properties
            objinfo['id'] = objid
            objinfo['fqname'] = self.i2n(objid)
            if not objinfo['name']:
                objinfo['name'] = '/id/' + objid

            if not fields:
                result.append(objid)
            elif fields == '*':
                result.append(objinfo)
            else:
                result.append([objinfo.get(fld) for fld in fields])

        return result
