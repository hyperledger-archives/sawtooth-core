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

import random
import logging
import ConfigParser
import hashlib
import threading
import time

from collections import namedtuple
from datetime import datetime
from itertools import product
from string import ascii_letters

import yaml

from sawtooth.simulator_workload import SawtoothWorkload
from sawtooth.client import TransactionStatus
from sawtooth.exceptions import InvalidTransactionError
from sawtooth.exceptions import MessageException

from journal.object_store import UniqueConstraintError

from sawtooth_bond.bond_client import BondClient

LOGGER = logging.getLogger(__name__)

BondIdentifier = namedtuple('BondIdentifier', ['isin', 'cusip'])
Client = namedtuple('Client', ['organizations', 'bond_client', 'id'])


class BondWorkload(SawtoothWorkload):
    """
    This workload is for the Sawtooth bond transaction family.
    """

    @staticmethod
    def _generate_next_pricing_source():
        """
        Pricing sources are a unique 4-letter value for organizations that want
        to issue bond quotes.  This function will generate unique ones...at
        least it will generate 52^3 of them with values Z[a-zA-Z]3, starting
        with Zaaa and ending with ZZZZ.

        Returns:
            The next pricing source.
        """
        for combination in product(ascii_letters, repeat=3):
            yield 'Z{}'.format(''.join(combination))

    def __init__(self, delegate, config):
        super(BondWorkload, self).__init__(delegate, config)

        self._clients = []
        self._bond_ids = []
        self._order_to_quote_ratio = 10
        self._lock = threading.Lock()

        try:
            self._order_to_quote_ratio = \
                int(config.get('BondWorkload', 'order_to_quote_ratio'))
            if self._order_to_quote_ratio <= 0:
                raise \
                    ValueError(
                        'Order to quote ratio must be greater than zero')
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            pass

        self._orders_since_last_quote = 0
        self._pricing_source_generator = self._generate_next_pricing_source()

    def on_will_start(self):
        # Note that the simulator will have already let us know about
        # the initial list of validators.  So, we can simply use the
        # first client to submit our initial transactions.

        try:
            # Before the simulator starts, we will do any setup of
            # participants, etc., if the configuration tells us to do so

            setup_file = self.config.get('BondWorkload', 'setup_file')

            # Now read in the setup file, which is to be in YAML format,
            # and process the transactions.
            with open(setup_file) as fd:
                data = yaml.load(fd)

            # Unless we know about at least one validator, we cannot load
            # the setup date
            if len(self._clients) > 0:
                transactions = []
                organizations = []

                with self._create_temporary_key_file() as key_file:
                    client = \
                        BondClient(
                            base_url=self._clients[0].bond_client.base_url,
                            keyfile=key_file.name)

                    LOGGER.info(
                        'Submit initial transactions from %s to %s',
                        setup_file,
                        client.base_url)
                    for transaction in data['Transactions']:
                        try:
                            transactions.append(
                                client.send_bond_txn(transaction))

                            # Add any organizations with a pricing source so
                            # later we can add market maker role authorizations
                            organizations.extend(
                                [u for u in transaction['Updates']
                                 if u['UpdateType'] == 'CreateOrganization'
                                 and u.get('PricingSource') is not None
                                 and u.get('ObjectId') is not None])
                        except (InvalidTransactionError,
                                UniqueConstraintError) as err:
                            LOGGER.error('Transaction failed: %s', err)

                    LOGGER.info(
                        'Wait for transactions to commit on %s',
                        client.base_url)
                    client.wait_for_commit()

                # It is not enough to have waited for the client to which
                # bond setup transactions were issued to commit.  We really
                # want to make sure that all of the validators have the
                # transactions before we begin as once things get started we
                # will issue new transactions to random validators.
                LOGGER.info(
                    'Wait for transactions to propagate to all validators')
                self._wait_for_all_to_commit(transactions)

                # Because we may have loaded organizations that can create
                # quotes (i.e., have a pricing source), we want to be sure
                # to catch them here as well since they may not have
                # already been in the system.  So, run through the
                # transactions and look for any updates that create an
                # organization with a pricing source and add market maker
                # role authorizations by the participants.
                for client in self._clients:
                    # Refresh the client state to ensure that we get the
                    # local store in sync so that local validation of
                    # transactions doesn't fail.

                    for organization in organizations:
                        try:
                            LOGGER.info(
                                'Add marketmaker role authorization to '
                                '%s (%s) by participant {%s}',
                                organization.get('Name'),
                                organization.get('PricingSource'),
                                client.id)
                            client.bond_client.add_authorization_to_org(
                                object_id=organization.get('ObjectId'),
                                role='marketmaker',
                                participant_id=client.id)

                            # Because we succeeded, we can add the
                            # organization to the client so it can use it
                            # when it starts issuing orders/quotes.  We will
                            # also keep the transaction ID so we can wi
                            client.organizations.append({
                                'object-id': organization.get('ObjectId'),
                                'name': organization.get('Name'),
                                'pricing-source':
                                    organization.get('PricingSource')
                            })
                        except (InvalidTransactionError,
                                UniqueConstraintError) as err:
                            LOGGER.error('Transaction failed: %s', err)
            else:
                LOGGER.warning(
                    'Cannot pre-load bond transactions as we do not have any '
                    'known validators')

        except ConfigParser.NoSectionError:
            LOGGER.warning(
                'Configuration does not contain BondWorkload section. '
                'Will not pre-load bond transactions before starting.')
        except ConfigParser.NoOptionError:
            LOGGER.warning(
                'Configuration BondWorkload section does not contain a '
                'setup_file option.  Will not pre-load bond transactions '
                'before starting.')
        except IOError as err:
            LOGGER.warning('Failed to pre-load bond transactions: %s', err)

        # Ensure that all clients have fresh state of the new transactions
        # that we submitted and that all transactions submitted to the client
        # are committed
        for client in self._clients:
            LOGGER.info(
                'Wait for all transactions on %s to commit',
                client.bond_client.base_url)
            client.bond_client.wait_for_commit()

        # Fetch the state from the first client and find the list of bonds so
        # we can use them to issue orders
        state = self._clients[0].bond_client.get_all_store_objects()
        bond_list = [b for b in state.iteritems() if
                     b[1]["object-type"] == 'bond']
        self._bond_ids = \
            [BondIdentifier(isin=b.get('isin'), cusip=b.get('cusip'))
             for _, b in bond_list]
        if len(self._bond_ids) == 0:
            raise \
                Exception('There are no bonds to issue orders/quotes against')

    def on_will_stop(self):
        pass

    def on_validator_discovered(self, url):
        # We need a key file for the client then create a new client and add
        # it to our cadre of clients to use.  For each client, we are going to
        # get the list of organizations it knows about.  For any organization
        # that has a pricing source (i.e., can be a market maker) that is not
        # one of our made up ones (i.e., starts with Z), we are going to add
        # an authorization to it for the newly-created participant and
        # role of market maker.  If the client has no such organizations, we
        # will create one of our own.  Later on we will be able to issue orders
        # and quotes against this(these) organization(s).  It is important
        # that orders (buy/sell) and quotes be issued from the same client
        # that creates the participant.
        with self._create_temporary_key_file() as key_file:
            try:
                client = BondClient(base_url=url, keyfile=key_file.name)

                # Participant and organization names are limited to 16
                # characters and a full ISO formatted date/time is too long
                # so generate something that can be used as a fairly random
                # string of 14 characters
                random_name = \
                    hashlib.md5(datetime.now().isoformat()).hexdigest()

                participant_name = 'P_{0:.14s}'.format(random_name)
                participant_id = 'intel_simparticipant_{0}'.format(random_name)

                LOGGER.info(
                    'Create participant %s with ID %s for %s',
                    participant_name,
                    participant_id,
                    client.base_url)

                client.create_participant(
                    username=participant_name,
                    object_id=participant_id)

                # Get the list of organizations that have a pricing source
                # that doesn't start with Z (i.e., is one we made up).
                state = client.get_all_store_objects()
                organizations = []
                org_list = [x[1] for x in state.iteritems() if
                            x[1]["object-type"] == 'organization']
                for org in org_list:
                    pricing_source = org.get('pricing-source')
                    if pricing_source is not None \
                            and not pricing_source.startswith('Z'):
                        organizations.append(org)

                # If there were none, then we need to create one so that we
                # at least have one market maker for this client to issue
                # quotes/orders against.
                if len(organizations) == 0:
                    marketmaker_name = 'M_{0:.14s}'.format(random_name)
                    marketmaker_id = \
                        'intel_simmarketmaker_{0}'.format(random_name)

                    # Just in case there are market makers left lying around
                    # from a previous run we will keep trying until we hit a
                    # unique pricing source.  Once successful, add this
                    # organization to the list
                    while True:
                        try:
                            pricing_source = \
                                next(self._pricing_source_generator)
                            client.create_org(
                                name=marketmaker_name,
                                object_id=marketmaker_id,
                                pricing_src=pricing_source)
                            break
                        except InvalidTransactionError:
                            pass

                    organizations.append({
                        'object-id': marketmaker_id,
                        'name': marketmaker_name,
                        'pricing-source': pricing_source
                    })

                    LOGGER.info(
                        'Create marketmaker %s with pricing source %s and '
                        'ID %s for %s',
                        marketmaker_name,
                        pricing_source,
                        marketmaker_id,
                        client.base_url)

                # Now, we need to add a participant/market maker role
                # authorization to each organization
                for organization in organizations:
                    LOGGER.info(
                        'Add marketmaker role authorization to %s (%s) by '
                        'participant %s',
                        organization.get('name'),
                        organization.get('pricing-source'),
                        participant_id)
                    client.add_authorization_to_org(
                        object_id=organization.get('object-id'),
                        role='marketmaker',
                        participant_id=participant_id)

                # Add the client to our list so that we can choose from it
                # when randomly issuing new transactions.
                with self._lock:
                    self._clients.append(
                        Client(
                            organizations=organizations,
                            bond_client=client,
                            id=participant_id))
            except (InvalidTransactionError, MessageException) as err:
                LOGGER.error(
                    'Failed to create participant and authorize '
                    'organization(s): %s',
                    err)

    def on_validator_removed(self, url):
        # If a validator goes away, we will remove the corresponding
        # client objects
        with self._lock:
            self._clients = \
                [c for c in self._clients if c.bond_client.base_url != url]

    def on_all_transactions_committed(self):
        self._create_new_transaction()

    def on_transaction_committed(self, transaction_id):
        self._create_new_transaction()

    def on_transaction_not_yet_committed(self, transaction_id):
        self._create_new_transaction()
        return True

    def _wait_for_all_to_commit(self, transactions):
        # make sure that all of the validators have the transactions
        # committed.
        while len(transactions) > 0:
            LOGGER.info(
                'Waiting for %d transaction(s) to commit on %d '
                'validator(s)',
                len(transactions),
                len(self._clients))
            pending = []
            for transaction in transactions:
                for client in self._clients:
                    if client.bond_client.get_transaction_status(
                            transaction) != \
                            TransactionStatus.committed:
                        LOGGER.info(
                            'Transaction %s has not committed on %s',
                            transaction,
                            client.bond_client.base_url)
                        pending.append(transaction)
                        break
            transactions = pending

            # If we have some pending, let's sleep for a small amount of
            # time as we don't need to keep askign as quickly as we can
            if len(pending) > 0:
                time.sleep(5)

    def _submit_order(self, client, organization):
        # Create a random order (action type,
        # 1000 <= quantity <= 10000, firm ID, and isin/cusip)
        action = random.choice(['Buy', 'Sell'])
        quantity = 1000 * random.randint(1, 10)
        bond_id = random.choice(self._bond_ids)

        LOGGER.info(
            'Create order: action=%s, quantity=%d, firm=%s, isin=%s, cusip=%s',
            action,
            quantity,
            organization.get('name'),
            bond_id.isin,
            bond_id.cusip)

        transaction_id = \
            client.create_order(
                action=action,
                order_type='Market',
                firm_id=organization.get('object-id'),
                quantity=quantity,
                isin=bond_id.isin,
                cusip=bond_id.cusip)

        LOGGER.info(
            'Created order with transaction ID %s on %s',
            transaction_id,
            client.base_url)

        return transaction_id

    def _submit_quote(self, client, organization):
        # Create a random quote:
        # '100-00 0/8' <= bid price <= '105-31 7/8',
        # 100000 <= bid quantity <= 500000
        # bid price <= ask price <= '105-31 7/8'
        # 100000 <= ask quantity <= 500000
        # random isin/cusip
        bid_whole = random.randint(100, 105)
        bid_ticks = random.randint(0, 31)
        bid_remainder = random.randint(0, 7)
        bid_price = \
            '{0}-{1:02d} {2}/8'.format(
                bid_whole,
                bid_ticks,
                bid_remainder)
        bid_quantity = 100000 + 1000 * random.randint(0, 400)
        ask_whole = random.randint(bid_whole, 105)
        ask_ticks = random.randint(bid_ticks, 31)
        ask_remainder = random.randint(bid_remainder, 7)
        ask_price = \
            '{0}-{1:02d} {2}/8'.format(
                ask_whole,
                ask_ticks,
                ask_remainder)
        ask_quantity = 100000 + 1000 * random.randint(0, 400)
        bond_id = random.choice(self._bond_ids)

        LOGGER.info(
            'Create quote: bid price=%s, bid qty=%d, '
            'ask price=%s, ask qty=%d, pricing source=%s, isin=%s, '
            'cusip=%s',
            bid_price,
            bid_quantity,
            ask_price,
            ask_quantity,
            organization.get('pricing-source'),
            bond_id.isin,
            bond_id.cusip)

        transaction_id = \
            client.create_quote(
                firm=organization.get('pricing-source'),
                ask_qty=ask_quantity,
                ask_price=ask_price,
                bid_qty=bid_quantity,
                bid_price=bid_price,
                isin=bond_id.isin,
                cusip=bond_id.cusip)

        LOGGER.info(
            'Created quote with transaction ID %s on %s',
            transaction_id,
            client.base_url)

        return transaction_id

    def _create_new_transaction(self):
        if len(self._bond_ids) > 0:
            try:
                with self._lock:
                    # Grab a client at random if we have at least one
                    client = \
                        random.choice(self._clients) \
                        if len(self._clients) > 0 else None

                    # Optimistically assume we will issue an order
                    self._orders_since_last_quote += 1
                    will_issue_order = True

                    # However, check to see if we need to issue a quote
                    if self._orders_since_last_quote > \
                            self._order_to_quote_ratio:
                        will_issue_order = False
                        self._orders_since_last_quote = 0

                if client is not None:
                    # Pick a random organization from the client
                    organization = random.choice(client.organizations)

                    if will_issue_order:
                        transaction_id = \
                            self._submit_order(
                                client.bond_client,
                                organization)
                    else:
                        transaction_id = \
                            self._submit_quote(
                                client.bond_client,
                                organization)

                    self.delegate.on_new_transaction(
                        transaction_id,
                        client.bond_client)
            except InvalidTransactionError as err:
                LOGGER.error(
                    'Unable to successfully submit an order/quote: %s', err)
