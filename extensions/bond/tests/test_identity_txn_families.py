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

import unittest
import time

from gossip import signed_object
from journal.object_store import ObjectStore
from sawtooth_bond.txn_family import BondTransaction
from sawtooth_bond.updates.bond import CreateBondUpdate
from sawtooth_bond.updates.identity import CreateOrganizationUpdate
from sawtooth_bond.updates.identity import CreateParticipantUpdate
from sawtooth_bond.updates.trading import CreateOrderUpdate
from sawtooth_bond.updates.trading import CreateQuoteUpdate
from sawtooth.exceptions import InvalidTransactionError


class TestCreateOrganizationUpate(unittest.TestCase):

    def setUp(self):
        self.key = signed_object.generate_signing_key()
        participant = CreateParticipantUpdate("CreateParticipant", "testuser")
        object_id = participant._object_id
        transaction = BondTransaction({})
        transaction._updates = [participant]
        self.store = ObjectStore()
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        transaction.apply(self.store)

    def test_organization_is_valid_valid(self):
        transaction = BondTransaction({
            "UpdateType": "CreateOrganization",
            'Updates': [{"UpdateType": "CreateOrganization",
                         "name": "Test Bank",
                         "ticker": "T",
                         "pricing_source": "ABCD",
                         "authorization": []
                         }]
        })
        transaction.sign_object(self.key)

        try:
            transaction.check_valid(self.store)
            transaction.apply(self.store)

        except InvalidTransactionError:
            self.fail("This should be valid")

    def test_organization_is_valid_object_id(self):
        k = self.store.keys()[0]
        transaction = BondTransaction({
            "UpdateType": "CreateOrganization",
            'Updates': [{"UpdateType": "CreateOrganization",
                         "name": "Test Bank",
                         "ticker": "T",
                         "pricing_source": "ABCD",
                         "authorization": [],
                         "object_id": k
                         }]
        })
        transaction.sign_object(self.key)

        try:
            transaction.check_valid(self.store)
            self.fail("Object_id already exists")
        except InvalidTransactionError:
            pass

    def test_organization_is_valid_name(self):
        # create organization
        transaction = BondTransaction({
            "UpdateType": "CreateOrganization",
            'Updates': [{"UpdateType": "CreateOrganization",
                         "name": "Test Bank",
                         "ticker": "T",
                         "pricing_source": "ABCD",
                         "authorization": []
                         }]
        })
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        transaction.apply(self.store)

        # add organization with the same name
        transaction = BondTransaction({
            "UpdateType": "CreateOrganization",
            'Updates': [{"UpdateType": "CreateOrganization",
                         "name": "Test Bank",
                         "ticker": "F",
                         "pricing_source": "ABCf",
                         "authorization": []
                         }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("Name already exists")
        except InvalidTransactionError:
            pass

    def test_organization_is_valid_ticker(self):
        # create organization
        transaction = BondTransaction({
            "UpdateType": "CreateOrganization",
            'Updates': [{"UpdateType": "CreateOrganization",
                         "name": "Test Bank1",
                         "ticker": "T",
                         "pricing_source": "ABCD",
                         "authorization": []
                         }]
        })
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        transaction.apply(self.store)

        # add organization with the same name
        transaction = BondTransaction({
            "UpdateType": "CreateOrganization",
            'Updates': [{"UpdateType": "CreateOrganization",
                         "name": "Test Bank2",
                         "ticker": "T",
                         "pricing_source": "ABCf",
                         "authorization": []
                         }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("Ticker already exists")
        except InvalidTransactionError:
            pass

    def test_organization_is_valid_pricing_source(self):
        # create organization
        transaction = BondTransaction({
            "UpdateType": "CreateOrganization",
            'Updates': [{"UpdateType": "CreateOrganization",
                         "name": "Test Bank1",
                         "ticker": "T",
                         "pricing_source": "ABCD",
                         "authorization": []
                         }]
        })
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        transaction.apply(self.store)

        # add organization with the same name
        transaction = BondTransaction({
            "UpdateType": "CreateOrganization",
            'Updates': [{"UpdateType": "CreateOrganization",
                         "name": "Test Bank2",
                         "ticker": "F",
                         "pricing_source": "ABCD",
                         "authorization": []
                         }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("Pricing Source already exists")
        except InvalidTransactionError:
            pass

    def test_organization_is_valid_short_pricing_source(self):
        # create organization
        transaction = BondTransaction({
            "UpdateType": "CreateOrganization",
            'Updates': [{"UpdateType": "CreateOrganization",
                         "name": "Test Bank",
                         "ticker": "T",
                         "pricing_source": "A",
                         "authorization": []
                         }]
        })
        transaction.sign_object(self.key)

        try:
            transaction.check_valid(self.store)
            self.fail("Pricing Source is too short")
        except InvalidTransactionError:
            pass

    def test_organization_is_valid_bad_authorization_format(self):
        # create organization
        transaction = BondTransaction({
            "UpdateType": "CreateOrganization",
            'Updates': [{"UpdateType": "CreateOrganization",
                         "name": "Test Bank",
                         "ticker": "T",
                         "pricing_source": "ABCD",
                         "authorization": [{"ParticipantId": "object_id"}]
                         }]
        })
        transaction.sign_object(self.key)

        try:
            transaction.check_valid(self.store)
            self.fail("Needs ParticipantId and Roles")
        except InvalidTransactionError:
            pass

    def test_organization_is_valid_authorization_participant_roles(self):
        # create organization
        transaction = BondTransaction({
            "UpdateType": "CreateOrganization",
            'Updates': [{"UpdateType": "CreateOrganization",
                         "name": "Test Bank",
                         "ticker": "T",
                         "pricing_source": "ABCD",
                         "authorization": [{"ParticipantId": "object_id",
                                            "Role": "moneymaker"}]
                         }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("Role can only be trader or marketmaker")
        except InvalidTransactionError:
            pass

    def test_organization_is_valid_authorization_participant_id(self):
        transaction = BondTransaction({
            "UpdateType": "CreateOrganization",
            'Updates': [{"UpdateType": "CreateOrganization",
                         "name": "Test Bank",
                         "ticker": "T",
                         "pricing_source": "ABCD",
                         "authorization": [{"ParticipantId": "made_up_id",
                                            "Role": "marketmaker"}]
                         }]
        })

        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("Participant does not exist")
        except InvalidTransactionError:
            pass

    def test_organization_is_valid_authorization_ref_count(self):
        p = self.store.keys()[0]
        transaction = BondTransaction({
            "UpdateType": "CreateOrganization",
            'Updates': [{"UpdateType": "CreateOrganization",
                         "name": "Test Bank",
                         "ticker": "T",
                         "pricing_source": "ABCD",
                         "authorization": [{"ParticipantId": p,
                                            "Role": "marketmaker"}]
                         }]
        })

        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        transaction.apply(self.store)

        org = self.store.lookup("organization:name", "Test Bank")
        self.assertEquals(org["ref-count"], 1)


class TestUpdateOrganizationUpdate(unittest.TestCase):

    def setUp(self):
        self.key = signed_object.generate_signing_key()
        participant = CreateParticipantUpdate("CreateParticipant", "testuser")
        object_id = participant._object_id
        transaction = BondTransaction({})
        transaction._updates = [participant]
        self.store = ObjectStore()
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        transaction.apply(self.store)

        transaction = BondTransaction({
            "UpdateType": "CreateOrganization",
            'Updates': [{"UpdateType": "CreateOrganization",
                         "name": "Test Bank",
                         "ticker": "T",
                         "pricing_source": "ABCD",
                         "authorization": [],
                         "industry": "Test"
                         }]
        })
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        transaction.apply(self.store)

    def test_organization_update_valid(self):
        org = self.store.lookup("organization:name", "Test Bank")
        org_id = org["object-id"]
        transaction = BondTransaction({
            "UpdateType": "UpdateOrganization",
            'Updates': [{"UpdateType": "UpdateOrganization",
                         "name": "Best Bank",
                         "object_id": org["object-id"]

                         }]
        })
        try:
            transaction.sign_object(self.key)
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

        org = self.store.lookup("organization:name", "Best Bank")
        self.assertEquals(org_id, org["object-id"])

    def test_organization_update_creator_id(self):
        key = signed_object.generate_signing_key()
        org = self.store.lookup("organization:name", "Test Bank")
        transaction = BondTransaction({
            "UpdateType": "UpdateOrganization",
            'Updates': [{"UpdateType": "UpdateOrganization",
                         "name": "Best Bank",
                         "object_id": org["object-id"]

                         }]
        })
        transaction.sign_object(key)
        try:
            transaction.check_valid(self.store)
            self.fail("Wrong creator")
        except InvalidTransactionError:
            pass

    def test_organization_update_ticker(self):
        org = self.store.lookup("organization:name", "Test Bank")
        transaction = BondTransaction({
            "UpdateType": "UpdateOrganization",
            'Updates': [{"UpdateType": "UpdateOrganization",
                         "ticker": "T",
                         "object_id": org["object-id"]

                         }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("Organization already has a ticker")
        except InvalidTransactionError:
            pass

    def test_organization_update_pricing_source(self):
        org = self.store.lookup("organization:name", "Test Bank")
        transaction = BondTransaction({
            "UpdateType": "UpdateOrganization",
            'Updates': [{"UpdateType": "UpdateOrganization",
                         "pricing_source": "EFGH",
                         "object_id": org["object-id"]

                         }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("Organization already has a pricing source")
        except InvalidTransactionError:
            pass

    def test_organization_update_name(self):
        org = self.store.lookup("organization:name", "Test Bank")
        transaction = BondTransaction({
            "UpdateType": "UpdateOrganization",
            'Updates': [{"UpdateType": "UpdateOrganization",
                         "name": "Test Bank",
                         "object_id": org["object-id"]

                         }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("Organization already has a pricing source")
        except InvalidTransactionError:
            pass

    def test_organization_update_industry(self):
        org = self.store.lookup("organization:name", "Test Bank")
        transaction = BondTransaction({
            "UpdateType": "UpdateOrganization",
            'Updates': [{"UpdateType": "UpdateOrganization",
                         "object_id": org["object-id"],
                         "industry": "The Best Industry",

                         }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

        org = self.store.lookup("organization:name", "Test Bank")
        self.assertEquals(org["industry"], "The Best Industry")


class TestUpdateOrganizationAuthorizationUpdate(unittest.TestCase):

    def setUp(self):
        self.key = signed_object.generate_signing_key()
        participant = CreateParticipantUpdate("CreateParticipant", "testuser")
        object_id = participant._object_id
        transaction = BondTransaction({})
        transaction._updates = [participant]
        self.store = ObjectStore()
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        transaction.apply(self.store)

        transaction = BondTransaction({
            "UpdateType": "CreateOrganization",
            'Updates': [{"UpdateType": "CreateOrganization",
                         "name": "Test Bank",
                         "ticker": "T",
                         "pricing_source": "ABCD",
                         "authorization": [],
                         "industry": "Test"
                         }]
        })
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        transaction.apply(self.store)

    def test_organization_add_authorization_valid(self):
        organization = self.store.lookup("organization:name", "Test Bank")
        participant = self.store.lookup("participant:username", "testuser")
        transaction = BondTransaction({
            "UpdateType": "UpdateOrganizationAuthorization",
            'Updates': [{"UpdateType": "UpdateOrganizationAuthorization",
                         "object_id": organization["object-id"],
                         "action": "add",
                         "participant_id": participant["object-id"],
                         "role": "marketmaker"
                         }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should valid")

    def test_organization_add_authorization_role(self):
        organization = self.store.lookup("organization:name", "Test Bank")
        participant = self.store.lookup("participant:username", "testuser")
        transaction = BondTransaction({
            "UpdateType": "UpdateOrganizationAuthorization",
            'Updates': [{"UpdateType": "UpdateOrganizationAuthorization",
                         "object_id": organization["object-id"],
                         "action": "add",
                         "participant_id": participant["object-id"],
                         "role": "moneymaker"
                         }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("Bad Role")
        except InvalidTransactionError:
            pass

    def test_organization_add_authorization_object_id(self):
        organization = self.store.lookup("organization:name", "Test Bank")
        participant = self.store.lookup("participant:username", "testuser")
        transaction = BondTransaction({
            "UpdateType": "UpdateOrganizationAuthorization",
            'Updates': [{"UpdateType": "UpdateOrganizationAuthorization",
                         "object_id": "BadId",
                         "action": "add",
                         "participant_id": participant["object-id"],
                         "role": "moneymaker"
                         }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("Object Id doesnt exist")
        except InvalidTransactionError:
            pass

    def test_organization_add_authorization_valid_exists(self):
        organization = self.store.lookup("organization:name", "Test Bank")
        participant = self.store.lookup("participant:username", "testuser")
        transaction = BondTransaction({
            "UpdateType": "UpdateOrganizationAuthorization",
            'Updates': [{"UpdateType": "UpdateOrganizationAuthorization",
                         "object_id": organization["object-id"],
                         "action": "add",
                         "participant_id": participant["object-id"],
                         "role": "marketmaker"
                         }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should valid")

        transaction = BondTransaction({
            "UpdateType": "UpdateOrganizationAuthorization",
            'Updates': [{"UpdateType": "UpdateOrganizationAuthorization",
                         "object_id": organization["object-id"],
                         "action": "add",
                         "participant_id": participant["object-id"],
                         "role": "marketmaker"
                         }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("Participant already in Authorization list")
        except InvalidTransactionError:
            pass

    def test_organization_add_remove_self_authorization_valid(self):
        key = signed_object.generate_signing_key()
        firm = self.store.lookup("organization:name", "Test Bank")
        transaction = BondTransaction({
            "UpdateType": "CreateParticipant",
            'Updates': [{"UpdateType": "CreateParticipant",
                         "username": "NewUser",
                         "firm_id": firm["object-id"]
                         }]
        })

        try:
            transaction.sign_object(key)
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

        organization = self.store.lookup("organization:name", "Test Bank")
        participant = self.store.lookup("participant:username", "NewUser")
        transaction = BondTransaction({
            "UpdateType": "UpdateOrganizationAuthorization",
            'Updates': [{"UpdateType": "UpdateOrganizationAuthorization",
                         "object_id": organization["object-id"],
                         "action": "add",
                         "participant_id": participant["object-id"],
                         "role": "marketmaker"
                         }]
        })
        transaction.sign_object(key)

        try:
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should valid, Added by self")

    def test_organization_add_self_authorization_valid(self):
        key = signed_object.generate_signing_key()
        firm = self.store.lookup("organization:name", "Test Bank")
        transaction = BondTransaction({
            "UpdateType": "CreateParticipant",
            'Updates': [{"UpdateType": "CreateParticipant",
                         "username": "NewUser",
                         "firm_id": firm["object-id"]
                         }]
        })

        try:
            transaction.sign_object(key)
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

        organization = self.store.lookup("organization:name", "Test Bank")
        participant = self.store.lookup("participant:username", "NewUser")
        transaction = BondTransaction({
            "UpdateType": "UpdateOrganizationAuthorization",
            'Updates': [{"UpdateType": "UpdateOrganizationAuthorization",
                         "object_id": organization["object-id"],
                         "action": "add",
                         "participant_id": participant["object-id"],
                         "role": "marketmaker"
                         }]
        })
        transaction.sign_object(self.key)

        try:
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should valid, Added by Creator")

    def test_organization_add_remove_self_authorization(self):
        key = signed_object.generate_signing_key()
        firm = self.store.lookup("organization:name", "Test Bank")
        transaction = BondTransaction({
            "UpdateType": "CreateParticipant",
            'Updates': [{"UpdateType": "CreateParticipant",
                         "username": "NewUser",
                         "firm_id": firm["object-id"]
                         }]
        })

        try:
            transaction.sign_object(key)
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

        organization = self.store.lookup("organization:name", "Test Bank")
        participant = self.store.lookup("participant:username", "NewUser")
        transaction = BondTransaction({
            "UpdateType": "UpdateOrganizationAuthorization",
            'Updates': [{"UpdateType": "UpdateOrganizationAuthorization",
                         "object_id": organization["object-id"],
                         "action": "add",
                         "participant_id": participant["object-id"],
                         "role": "marketmaker"
                         }]
        })
        transaction.sign_object(self.key)

        try:
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should valid, Added by Creator")

        organization = self.store.lookup("organization:name", "Test Bank")
        participant = self.store.lookup("participant:username", "NewUser")
        transaction = BondTransaction({
            "UpdateType": "UpdateOrganizationAuthorization",
            'Updates': [{"UpdateType": "UpdateOrganizationAuthorization",
                         "object_id": organization["object-id"],
                         "action": "remove",
                         "participant_id": participant["object-id"],
                         "role": "marketmaker"
                         }]
        })
        transaction.sign_object(key)
        transaction.check_valid(self.store)
        try:
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

    def test_organization_add_remove_others_authorization(self):
        organization = self.store.lookup("organization:name", "Test Bank")
        participant = self.store.lookup("participant:username", "testuser")
        transaction = BondTransaction({
            "UpdateType": "UpdateOrganizationAuthorization",
            'Updates': [{"UpdateType": "UpdateOrganizationAuthorization",
                         "object_id": organization["object-id"],
                         "action": "add",
                         "participant_id": participant["object-id"],
                         "role": "marketmaker"
                         }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

        organization = self.store.lookup("organization:name", "Test Bank")
        participant = self.store.lookup("participant:username", "testuser")
        transaction = BondTransaction({
            "UpdateType": "UpdateOrganizationAuthorization",
            'Updates': [{"UpdateType": "UpdateOrganizationAuthorization",
                         "object_id": organization["object-id"],
                         "action": "remove",
                         "participant_id": participant["object-id"],
                         "role": "marketmaker"
                         }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")


class TestDeleteOrganizationUpdate(unittest.TestCase):
    def setUp(self):
        self.key = signed_object.generate_signing_key()
        participant = CreateParticipantUpdate("CreateParticipant", "testuser")
        object_id = participant._object_id
        transaction = BondTransaction({})
        transaction._updates = [participant]
        self.store = ObjectStore()
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        transaction.apply(self.store)

        transaction = BondTransaction({
            "UpdateType": "CreateOrganization",
            'Updates': [{"UpdateType": "CreateOrganization",
                         "name": "Test Bank",
                         "ticker": "T",
                         "pricing_source": "ABCD",
                         "authorization": [],
                         "industry": "Test"
                         }]
        })
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        transaction.apply(self.store)

    def test_organization_delete_valid(self):
        organization = self.store.lookup("organization:name", "Test Bank")
        transaction = BondTransaction({
            "UpdateType": "DeleteOrganization",
            'Updates': [{"UpdateType": "DeleteOrganization",
                         "object_id": organization["object-id"]
                         }]
        })
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        transaction.apply(self.store)

    def test_organization_delete_creator_id(self):
        key = signed_object.generate_signing_key()
        organization = self.store.lookup("organization:name", "Test Bank")
        transaction = BondTransaction({
            "UpdateType": "DeleteOrganization",
            'Updates': [{"UpdateType": "DeleteOrganization",
                         "object_id": organization["object-id"]
                         }]
        })
        transaction.sign_object(key)
        try:
            transaction.check_valid(self.store)
            self.fail("Can only be deleted by Creator")
        except InvalidTransactionError:
            pass

    def test_organization_delete_refcount(self):
        organization = self.store.lookup("organization:name", "Test Bank")
        participant = self.store.lookup("participant:username", "testuser")
        transaction = BondTransaction({
            "UpdateType": "UpdateOrganizationAuthorization",
            'Updates': [{"UpdateType": "UpdateOrganizationAuthorization",
                         "object_id": organization["object-id"],
                         "action": "add",
                         "participant_id": participant["object-id"],
                         "role": "marketmaker"
                         }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should valid")

        organization = self.store.lookup("organization:name", "Test Bank")
        transaction = BondTransaction({
            "UpdateType": "DeleteOrganization",
            'Updates': [{"UpdateType": "DeleteOrganization",
                         "object_id": organization["object-id"]
                         }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("Refcount must be zero")
        except:
            pass


class TestCreateParticipantUpdate(unittest.TestCase):

    def setUp(self):
        self.store = ObjectStore()
        key = signed_object.generate_signing_key()
        transaction = BondTransaction({
            "UpdateType": "CreateParticipant",
            'Updates': [{"UpdateType": "CreateParticipant",
                         "username": "FirstUser",
                         }]
        })

        try:
            transaction.sign_object(key)
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

        transaction = BondTransaction({
            "UpdateType": "CreateOrganization",
            'Updates': [{"UpdateType": "CreateOrganization",
                         "name": "FirstBank",
                         "ticker": "T",
                         "pricing_source": "ABCD",
                         "authorization": []
                         }]
        })
        transaction.sign_object(key)

        try:
            transaction.check_valid(self.store)
            transaction.apply(self.store)

        except InvalidTransactionError:
            self.fail("This should be valid")

    def test_participant_is_valid_valid(self):
        key = signed_object.generate_signing_key()
        firm = self.store.lookup("organization:name", "FirstBank")
        transaction = BondTransaction({
            "UpdateType": "CreateParticipant",
            'Updates': [{"UpdateType": "CreateParticipant",
                         "username": "testusers",
                         "firm_id": firm["object-id"]
                         }]
        })

        try:
            transaction.sign_object(key)
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

    def test_participant_is_valid_object_id(self):
        key = signed_object.generate_signing_key()
        object_id = self.store.keys()[0]
        transaction = BondTransaction({
            "UpdateType": "CreateParticipant",
            'Updates': [{"UpdateType": "CreateParticipant",
                         "username": "testusers",
                         "object_id": object_id
                         }]
        })
        transaction.sign_object(key)
        try:
            transaction.check_valid(self.store)
            self.fail("Object_id already exists")
        except InvalidTransactionError:
            pass

    def test_participant_is_valid_username(self):
            key = signed_object.generate_signing_key()
            transaction = BondTransaction({
                "UpdateType": "CreateParticipant",
                'Updates': [{"UpdateType": "CreateParticipant",
                             "username": "FirstUser",
                             }]
            })
            transaction.sign_object(key)
            try:
                transaction.check_valid(self.store)
                self.fail("Username already exists")
            except InvalidTransactionError:
                pass

    def test_participant_is_valid_username_length(self):
        key = signed_object.generate_signing_key()
        transaction = BondTransaction({
            "UpdateType": "CreateParticipant",
            'Updates': [{"UpdateType": "CreateParticipant",
                         "username": "F",
                         }]
        })
        transaction.sign_object(key)
        try:
            transaction.check_valid(self.store)
            self.fail("Username is too short")
        except InvalidTransactionError:
            pass

    def test_participant_is_valid_firm(self):
        key = signed_object.generate_signing_key()
        transaction = BondTransaction({
            "UpdateType": "CreateParticipant",
            'Updates': [{"UpdateType": "CreateParticipant",
                         "username": "F",
                         "firm_id": "badFirmId"
                         }]
        })
        transaction.sign_object(key)
        try:
            transaction.check_valid(self.store)
            self.fail("Username is too short")
        except InvalidTransactionError:
            pass

    def test_correct_refcount_when_adding_participant(self):
        key = signed_object.generate_signing_key()
        firm = self.store.lookup("organization:name", "FirstBank")
        transaction = BondTransaction({
            "UpdateType": "CreateParticipant",
            'Updates': [{"UpdateType": "CreateParticipant",
                         "username": "testusers",
                         "firm_id": firm["object-id"]
                         }]
        })

        try:
            transaction.sign_object(key)
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

        firm = self.store.lookup("organization:name", "FirstBank")
        self.assertEquals(firm["ref-count"], 1)


class TestUpdateParticipantUpdate(unittest.TestCase):

    def setUp(self):
        self.store = ObjectStore()
        self.key = signed_object.generate_signing_key()
        transaction = BondTransaction({
            "UpdateType": "CreateParticipant",
            'Updates': [{"UpdateType": "CreateParticipant",
                         "username": "FirstUser",
                         }]
        })

        try:
            transaction.sign_object(self.key)
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            pass

        transaction = BondTransaction({
            "UpdateType": "CreateOrganization",
            'Updates': [{"UpdateType": "CreateOrganization",
                         "name": "FirstBank",
                         "ticker": "T",
                         "pricing_source": "ABCD",
                         "authorization": []
                         }]
        })
        transaction.sign_object(self.key)

        try:
            transaction.check_valid(self.store)
            transaction.apply(self.store)

        except InvalidTransactionError:
            pass

    def test_particpant_update_valid(self):
        participant = self.store.lookup("participant:username", 'FirstUser')
        part_id = participant["object-id"]
        firm = self.store.lookup("organization:name", 'FirstBank')
        transaction = BondTransaction({
            "UpdateType": "UpdateParticipant",
            'Updates': [{"UpdateType": "UpdateParticipant",
                         "username": "SameUser",
                         "firm_id": firm["object-id"],
                         "object_id": part_id
                         }]
        })
        transaction.sign_object(self.key)

        try:
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")
            pass

        participant = self.store.lookup("participant:object-id", part_id)
        self.assertEquals(participant["username"], "SameUser")
        self.assertEquals(participant["firm-id"], firm["object-id"])

    def test_participant_update_creator_id(self):
        key = signed_object.generate_signing_key()
        participant = self.store.lookup("participant:username", 'FirstUser')
        part_id = participant["object-id"]
        firm = self.store.lookup("organization:name", 'FirstBank')
        transaction = BondTransaction({
            "UpdateType": "UpdateParticipant",
            'Updates': [{"UpdateType": "UpdateParticipant",
                         "username": "SameUser",
                         "firm_id": firm["object-id"],
                         "object_id": part_id
                         }]
        })
        transaction.sign_object(key)

        try:
            transaction.check_valid(self.store)
            self.fail("Wrong Creator")
        except InvalidTransactionError:
            pass

    def test_participant_update_username(self):
        key = signed_object.generate_signing_key()
        participant = self.store.lookup("participant:username", 'FirstUser')
        part_id = participant["object-id"]
        firm = self.store.lookup("organization:name", 'FirstBank')
        transaction = BondTransaction({
            "UpdateType": "UpdateParticipant",
            'Updates': [{"UpdateType": "UpdateParticipant",
                         "username": "FirstUser",
                         "firm_id": firm["object-id"],
                         "object_id": part_id
                         }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("Name already exists")
        except InvalidTransactionError:
            pass

    def test_participant_update_firm_id(self):
        participant = self.store.lookup("participant:username", 'FirstUser')
        part_id = participant["object-id"]
        firm = self.store.lookup("organization:name", 'FirstBank')
        transaction = BondTransaction({
            "UpdateType": "UpdateParticipant",
            'Updates': [{"UpdateType": "UpdateParticipant",
                         "username": "SameUser",
                         "firm_id": "BadId",
                         "object_id": part_id
                         }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("Firm ID does not exist")
        except InvalidTransactionError:
            pass


class TestCreateOrderUpdate(unittest.TestCase):
    def setUp(self):
        self.key = signed_object.generate_signing_key()
        self.store = ObjectStore()
        transaction = BondTransaction({})
        participant = CreateParticipantUpdate('CreateParticipant', 'TestName')
        transaction._updates = [participant]
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        transaction.apply(self.store)

        organization = CreateOrganizationUpdate('CreateOrganization',
                                                'TestOrg', ticker='T',
                                                pricing_source='TEST',
                                                authorization=[])
        self.firm_id = organization._object_id
        transaction._updates = [organization]
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        transaction.apply(self.store)
        transaction = BondTransaction({
            'Updates': [{
                'UpdateType': 'Clock',
                'Blocknum': 0,
                'PreviousBlockId': 0,
                'Timestamp': time.time()
            }]
        })
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        transaction.apply(self.store)

        bond = CreateBondUpdate('CreateBond', issuer='T',
                                amount_outstanding=42671000000,
                                isin='US912828R770',
                                cusip='912828R77', corporate_debt_ratings=[],
                                coupon_benchmark=None, coupon_rate=.15,
                                coupon_type='Fixed',
                                coupon_frequency='Quarterly',
                                first_coupon_date='03/01/2012',
                                maturity_date='10/20/2015',
                                face_value=10000)
        transaction._updates = [bond]

        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        transaction.apply(self.store)
        org_obj = self.store.lookup('organization:ticker', 'T')
        self.org_ref_count = org_obj['ref-count']

    def test_valid_order(self):
        transaction = BondTransaction({
            'UpdateType': 'CreateOrder',
            'Updates': [{'UpdateType': 'CreateOrder', 'Action': 'Buy',
                         'Quantity': 1000000, 'OrderType': 'Market',
                         'Isin': 'US912828R770', 'FirmId': self.firm_id}]
        })
        try:
            transaction.sign_object(self.key)
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This is a correct CreateOrder")

    def test_missing_required_attributes(self):
        update = {'UpdateType': 'CreateOrder', 'Action': 'Buy',
                  'Quantity': 1000000, 'OrderType': 'Market',
                  'Isin': 'US912828R770', 'FirmId': self.firm_id}
        for attr in ['Action', 'OrderType', 'Isin', 'FirmId']:
            update[attr] = None
            transaction = BondTransaction({
                'UpdateType': 'CreateOrder',
                'Updates': [update]
            })
            try:
                transaction.sign_object(self.key)
                transaction.check_valid(self.store)
                self.fail("Missing required attribute: {}".format(attr))
            except InvalidTransactionError:
                pass

    def test_order_limit(self):
        transaction = BondTransaction(
            {'UpdateType': 'CreateOrder',
             'Updates': [{'UpdateType': 'CreateOrder', 'Action': 'Buy',
                          'Quantity': 1000000, 'OrderType': 'Limit',
                          'Isin': 'US912828R770',
                          'FirmId': self.firm_id}]})

        try:
            transaction.sign_object(self.key)
            transaction.check_valid(self.store)
            self.fail("Limit order requires LimitPrice or LimitYield")
        except InvalidTransactionError:
            pass

    def test_order_market(self):
        update = {'UpdateType': 'CreateOrder', 'Action': 'Buy',
                  'Quantity': 1000000, 'OrderType': 'Market',
                  'Isin': 'US912828R770', 'FirmId': self.firm_id}
        for attr, num in {'LimitPrice': '98-13+',
                          'LimitYield': .15}.iteritems():
            update[attr] = num
            transaction = BondTransaction({
                'UpdateType': 'CreateOrder',
                'Updates': [update]
            })
            try:
                transaction.sign_object(self.key)
                transaction.check_valid(self.store)
                self.fail("{} was set with a Market order".format(attr))
            except InvalidTransactionError:
                pass

    def test_no_isin_or_cusip(self):
        transaction = BondTransaction({
            'UpdateType': 'CreateOrder',
            'Updates': [{'UpdateType': 'CreateOrder', 'Action': 'Buy',
                         'Quantity': 1000000, 'OrderType': 'Market',
                        'FirmId': self.firm_id}]
        })
        try:
            transaction.sign_object(self.key)
            transaction.check_valid(self.store)
            self.fail("Isin and Cusip not set")
        except InvalidTransactionError:
            pass

    def test_isin_and_cusip_not_valid(self):
        update = {'UpdateType': 'CreateOrder', 'Action': 'Buy',
                  'Quantity': 1000000, 'OrderType': 'Market',
                  'Isin': 'NotValid', 'FirmId': self.firm_id}
        transaction1 = BondTransaction({
            'UpdateType': 'CreateOrder',
            'Updates': [update]
        })
        try:
            transaction1.sign_object(self.key)
            transaction1.check_valid(self.store)
            self.fail("Not a correct isin")
        except InvalidTransactionError:
            pass

        update['Cusip'] = 'NotValid'
        transaction2 = BondTransaction({
            'UpdateType': 'CreateOrder',
            'Updates': [update]
        })
        try:
            transaction2.sign_object(self.key)
            transaction2.check_valid(self.store)
            self.fail("Neither isin nor cusip were valid")
        except InvalidTransactionError:
            pass
        del update['Isin']
        transaction3 = BondTransaction({
            'UpdateType': 'CreateOrder',
            'Updates': [update]
        })
        try:
            transaction3.sign_object(self.key)
            transaction3.check_valid(self.store)
            self.fail("Not a correct cusip")
        except InvalidTransactionError:
            pass
        transaction = BondTransaction({})
        bond = CreateBondUpdate('CreateBond', issuer='T',
                                amount_outstanding=42671000000, isin=None,
                                cusip='12345', corporate_debt_ratings=[],
                                coupon_benchmark=None, coupon_rate=.15,
                                coupon_type='Fixed',
                                coupon_frequency='Quarterly',
                                first_coupon_date='03/01/2012',
                                maturity_date='10/20/2015',
                                face_value=10000)
        transaction._update = [bond]
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        transaction.apply(self.store)

        transaction4 = BondTransaction({
            'UpdateType': 'CreateOrder',
            'Updates': [{'UpdateType': 'CreateOrder', 'Action': 'Buy',
                         'Quantity': 1000000, 'OrderType': 'Market',
                         'Isin': 'US912828R770',
                         'Cusip': '12345', 'FirmId': self.firm_id}]
        })
        try:
            transaction4.sign_object(self.key)
            transaction4.check_valid(self.store)
            self.fail("Cusip and Isin reference different bonds")
        except InvalidTransactionError:
            pass

    def test_ref_count(self):
        self.test_valid_order()
        org_obj = self.store.lookup('organization:ticker', 'T')
        self.assertEquals(org_obj['ref-count'], self.org_ref_count + 1)


class TestUpdateOrderUpdate(unittest.TestCase):
    def setUp(self):
        self.key = signed_object.generate_signing_key()
        self.store = ObjectStore()
        transaction = BondTransaction({})
        participant = CreateParticipantUpdate('CreateParticipant', 'TestName')
        transaction._updates = [participant]
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        transaction.apply(self.store)
        auth = {'ParticipantId': participant._object_id,
                'Role': 'marketmaker'}
        organization = CreateOrganizationUpdate('CreateOrganization',
                                                'TestOrg', ticker='T',
                                                pricing_source='TEST',
                                                authorization=[auth])
        self.firm_id = organization._object_id
        transaction._updates = [organization]
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        transaction.apply(self.store)

        transaction = BondTransaction({
            'Updates': [{
                'UpdateType': 'Clock',
                'Blocknum': 0,
                'PreviousBlockId': 0,
                'Timestamp': time.time()
            }]
        })
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        transaction.apply(self.store)

        bond = CreateBondUpdate('CreateBond', issuer='T',
                                amount_outstanding=42671000000,
                                isin='US912828R770',
                                cusip='912828R77', corporate_debt_ratings=[],
                                coupon_benchmark=None, coupon_rate=.15,
                                coupon_type='Fixed',
                                coupon_frequency='Quarterly',
                                first_coupon_date='03/01/2012',
                                maturity_date='10/20/2015',
                                face_value=10000)
        transaction._updates = [bond]
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        transaction.apply(self.store)

        order = CreateOrderUpdate('CreateOrder', action='Buy',
                                  quantity=1000000, order_type='Market',
                                  isin='US912828R770',
                                  firm_id=organization._object_id)

        quote = CreateQuoteUpdate('CreateQuote', ask_price='95-15+',
                                  ask_qty=1000000, bid_price='85-78',
                                  bid_qty=1000000, firm='TEST',
                                  isin='US912828R770')
        transaction._updates = [order, quote]
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        transaction.apply(self.store)
        self.order_id = order._object_id
        self.quote_id = quote._object_id

    def test_valid_orderupdate(self):
        self.assertEqual(self.store[self.order_id]["status"], "Open")
        transaction = BondTransaction(
            {'UpdateType': 'UpdateOrder',
             'Updates': [{'UpdateType': 'UpdateOrder',
                          'ObjectId': self.order_id,
                          'QuoteId': self.quote_id,
                          'Status': 'Matched'}]})
        try:
            transaction.sign_object(self.key)
            transaction.check_valid(self.store)
            transaction.apply(self.store)
            order_obj = self.store.get(self.order_id, 'order')
            self.assertEqual(order_obj['quote-id'], self.quote_id,
                             "QuoteId has been set")
            quote_obj = self.store.get(self.quote_id, 'quote')
            self.assertEqual(quote_obj['ref-count'], 1,
                             "Quote has ref-count updated")
            self.assertEqual(self.store[self.order_id]["status"], "Matched")
        except InvalidTransactionError:
            self.fail("Correct UpdateOrder transaction")

    def test_wrong_object_id(self):
        transaction = BondTransaction(
            {'UpdateType': 'UpdateOrder',
             'Updates': [
                 {'UpdateType': 'UpdateOrder',
                  'ObjectId': 'NotValid',
                  'QuoteId': self.quote_id,
                  'Status': 'Matched'}]})
        try:
            transaction.sign_object(self.key)
            transaction.check_valid(self.store)
            transaction.apply(self.store)
            self.fail("Wrong Object Id will fail")
        except InvalidTransactionError:
            pass

    def test_object_id_not_an_order(self):
        transaction = BondTransaction(
            {'UpdateType': 'UpdateOrder',
             'Updates': [
                 {'UpdateType': 'UpdateOrder',
                  'ObjectId': self.quote_id,
                  'QuoteId': self.quote_id,
                  'Status': 'Matched'}]})

        try:
            transaction.sign_object(self.key)
            transaction.check_valid(self.store)
            transaction.apply(self.store)
            self.fail("Object Id is not an Order")
        except InvalidTransactionError:
            pass

    def test_wrong_order_id(self):
        transaction = BondTransaction(
            {'UpdateType': 'UpdateOrder',
             'Updates': [
                 {'UpdateType': 'UpdateOrder',
                  'ObjectId': self.order_id,
                  'QuoteId': 'NotValid',
                  'Status': 'Matched'}]})
        try:
            transaction.sign_object(self.key)
            transaction.check_valid(self.store)
            transaction.apply(self.store)
            self.fail("QuoteId is not in store")
        except InvalidTransactionError:
            pass

    def test_quote_id_not_a_quote(self):
        transaction = BondTransaction(
            {'UpdateType': 'UpdateOrder',
             'Updates': [
                 {'UpdateType': 'UpdateOrder',
                  'ObjectId': self.order_id,
                  'QuoteId': self.order_id,
                  'Status': 'Matched'}]})
        try:
            transaction.sign_object(self.key)
            transaction.check_valid(self.store)
            transaction.apply(self.store)
            self.fail("QuoteId is not a quote")
        except InvalidTransactionError:
            pass

    def test_quote_not_open(self):
        quote = self.store[self.quote_id]
        quote["status"] = "Closed"
        self.store[self.quote_id] = quote
        transaction = BondTransaction(
            {'UpdateType': 'UpdateOrder',
             'Updates': [{'UpdateType': 'UpdateOrder',
                          'ObjectId': self.order_id,
                          'QuoteId': self.quote_id,
                          'Status': 'Matched'}]})
        try:
            transaction.sign_object(self.key)
            transaction.check_valid(self.store)
            transaction.apply(self.store)
            self.fail("Quote has been closed")
        except InvalidTransactionError:
            pass

    def test_incorrect_quantity_buy(self):
        transaction = BondTransaction({})
        organization = self.store.lookup("organization:name", "TestOrg")
        quote = CreateQuoteUpdate('CreateQuote', ask_price='101',
                                  ask_qty=10000, bid_price='101',
                                  bid_qty=10000, firm='TEST',
                                  isin='US912828R770')
        transaction._updates = [quote]
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        transaction.apply(self.store)
        quote_id = quote._object_id

        transaction = BondTransaction(
            {'UpdateType': 'UpdateOrder',
             'Updates': [
                 {'UpdateType': 'UpdateOrder',
                  'ObjectId': self.order_id,
                  'QuoteId': quote_id,
                  'Status': 'Matched'}]})

        try:
            transaction.sign_object(self.key)
            transaction.check_valid(self.store)
            transaction.apply(self.store)
            self.fail("Quote Should not have enough quantity")
        except InvalidTransactionError:
            pass

    def test_incorrect_quantity_sell(self):
        transaction = BondTransaction({})
        organization = self.store.lookup("organization:name", "TestOrg")
        order = CreateOrderUpdate('CreateOrder', action='Sell',
                                  quantity=1000000, order_type='Market',
                                  isin='US912828R770',
                                  firm_id=organization["object-id"])

        quote = CreateQuoteUpdate('CreateQuote', ask_price='95-15+',
                                  ask_qty=100000, bid_price='85-78',
                                  bid_qty=100000, firm='TEST',
                                  isin='US912828R770')
        transaction._updates = [order, quote]
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        transaction.apply(self.store)
        order_id = order._object_id
        quote_id = quote._object_id

        transaction = BondTransaction(
            {'UpdateType': 'UpdateOrder',
             'Updates': [
                 {'UpdateType': 'UpdateOrder',
                  'ObjectId': order_id,
                  'QuoteId': quote_id,
                  'Status': 'Matched'}]})

        try:
            transaction.sign_object(self.key)
            transaction.check_valid(self.store)
            transaction.apply(self.store)
            self.fail("Quote Should not have enough quantity")
        except InvalidTransactionError:
            pass

    def test_close_quote(self):
        transaction = BondTransaction({})
        organization = self.store.lookup("organization:name", "TestOrg")
        order = CreateOrderUpdate('CreateOrder', action='Sell',
                                  quantity=100000, order_type='Market',
                                  isin='US912828R770',
                                  firm_id=organization["object-id"])

        quote = CreateQuoteUpdate('CreateQuote', ask_price='95-15+',
                                  ask_qty=100000, bid_price='85-78',
                                  bid_qty=100000, firm='TEST',
                                  isin='US912828R770')
        transaction._updates = [order, quote]
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        transaction.apply(self.store)
        order_id = order._object_id
        quote_id = quote._object_id

        transaction = BondTransaction(
            {'UpdateType': 'UpdateOrder',
             'Updates': [
                 {'UpdateType': 'UpdateOrder',
                  'ObjectId': order_id,
                  'QuoteId': quote_id,
                  'Status': 'Matched'}]})

        try:
            transaction.sign_object(self.key)
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fial("This should be valid")

        self.assertEqual(self.store[quote_id]["status"], "Closed")


class TestUpdateOrderUpdate(unittest.TestCase):
    def setUp(self):
        self.key = signed_object.generate_signing_key()
        self.store = ObjectStore()
        transaction = BondTransaction({})
        participant = CreateParticipantUpdate('CreateParticipant', 'TestName')
        transaction._updates = [participant]
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        transaction.apply(self.store)
        auth = {'ParticipantId': participant._object_id,
                'Role': 'marketmaker'}
        organization = CreateOrganizationUpdate('CreateOrganization',
                                                'TestOrg', ticker='T',
                                                pricing_source='TEST',
                                                authorization=[auth])
        self.firm_id = organization._object_id
        transaction._updates = [organization]
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        transaction.apply(self.store)

        transaction = BondTransaction({
            'Updates': [{
                'UpdateType': 'Clock',
                'Blocknum': 0,
                'PreviousBlockId': 0,
                'Timestamp': time.time()
            }]
        })
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        transaction.apply(self.store)

        bond = CreateBondUpdate('CreateBond', issuer='T',
                                amount_outstanding=42671000000,
                                isin='US912828R770',
                                cusip='912828R77', corporate_debt_ratings=[],
                                coupon_benchmark=None, coupon_rate=.15,
                                coupon_type='Fixed',
                                coupon_frequency='Quarterly',
                                maturity_date='10/20/2015',
                                first_coupon_date='04/01/2012',
                                face_value=10000)
        transaction._updates = [bond]
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        transaction.apply(self.store)

        order = CreateOrderUpdate('CreateOrder', action='Buy',
                                  quantity=1000000, order_type='Market',
                                  isin='US912828R770',
                                  firm_id=organization._object_id)

        transaction._updates = [order]
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        transaction.apply(self.store)
        self.order_id = order._object_id

    def test_valid_order_delete(self):
        self.assertEquals(len(self.store["open-orders"]["order-list"]), 1)
        self.assertEqual(self.store[self.order_id]["status"], "Open")
        transaction = BondTransaction(
            {'UpdateType': 'DeleteOrder',
             'Updates': [{'UpdateType': 'DeleteOrder',
                          'ObjectId': self.order_id}]})
        try:
            transaction.sign_object(self.key)
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("Correct DeleteOrder transaction")

        self.assertEquals(self.store["open-orders"]["order-list"], [])
