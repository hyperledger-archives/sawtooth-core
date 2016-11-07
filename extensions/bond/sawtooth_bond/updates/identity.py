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

from sawtooth.exceptions import InvalidTransactionError

from journal.transaction import Update


class CreateOrganizationUpdate(Update):
    def __init__(self, update_type, name, industry=None, ticker=None,
                 pricing_source=None, authorization=None, object_id=None,
                 nonce=None):
        super(CreateOrganizationUpdate, self).__init__(update_type)
        self._name = name
        self._industry = industry
        self._ticker = ticker
        self._pricing_source = pricing_source
        self._authorization = authorization
        self._nonce = nonce

        if object_id is None:
            self._object_id = self.create_id()
        else:
            self._object_id = object_id

    def check_valid(self, store, txn):
        # Verify that creator exists
        try:
            store.lookup('participant:key-id', txn.OriginatorID)
        except KeyError:
            raise InvalidTransactionError(
                "Creator was not found : {}".format(txn.OriginatorID))

        if self._object_id in store:
            raise InvalidTransactionError(
                "Object with id already exists: {}".format(self._object_id))

        try:
            store.lookup('organization:name', self._name)
            raise InvalidTransactionError(
                "Object with name already exists: {}".format(self._name))
        except KeyError:
            pass

        if self._ticker is not None:
            try:
                store.lookup('organization:ticker', self._ticker)
                raise InvalidTransactionError(
                    "Object with ticker already exists: {}"
                    .format(self._ticker))
            except KeyError:
                pass

        if self._pricing_source is not None:
            if len(self._pricing_source) != 4:
                raise InvalidTransactionError(
                    "Pricing source must be a four-character string: {}"
                    .format(self._pricing_source))

            try:
                store.lookup('organization:pricing-source',
                             self._pricing_source)
                raise InvalidTransactionError(
                    "Object with pricing source already exists: {}"
                    .format(self._pricing_source))
            except KeyError:
                pass

        if self._authorization is not None:
            for participant in self._authorization:
                if len(participant) != 2:
                    raise InvalidTransactionError(
                        "Must contain ParticpantId and Role for each entry"
                        " in Authorization: {}"
                        .format(participant))
                try:
                    participant_id = participant["ParticipantId"]
                    role = participant["Role"]

                except KeyError:
                    raise InvalidTransactionError(
                        "Must contain ParticipantId and Role for each entry"
                        " in Authorization: {}"
                        .format(participant))

                if role != "marketmaker" and role != "trader":
                    raise InvalidTransactionError("Role must be either "
                                                  "marketmaker or trader: {}"
                                                  .format(role))
                try:
                    store.get(participant_id,
                              object_type='participant')
                except KeyError:
                    raise InvalidTransactionError(
                        "No such participant: {}"
                        .format(participant['ParticipantId']))

    def apply(self, store, txn):
        creator = store.lookup('participant:key-id', txn.OriginatorID)
        obj = {
            'object-id': self._object_id,
            'object-type': 'organization',
            'name': self._name,
            'creator-id': creator["object-id"],
            "ref-count": 0
        }
        if self._industry is not None:
            obj['industry'] = self._industry
        if self._ticker is not None:
            obj['ticker'] = self._ticker
        if self._pricing_source is not None:
            obj['pricing-source'] = self._pricing_source
        if self._authorization is not None:
            obj['authorization'] = []
            for participant in self._authorization:
                obj['authorization'].append({
                    'participant-id': participant['ParticipantId'],
                    'role': participant['Role']
                })
                obj["ref-count"] += 1

        store[self._object_id] = obj

        if 'organizations' in store:
            orglist_obj = store['organizations']
            orglist_obj['organization-list'].append(self._object_id)
        else:
            orglist_obj = {
                'object-id': 'organizations',
                'object-type': 'organization-list',
                'organization-list': [self._object_id]
            }
        store['organizations'] = orglist_obj


class UpdateOrganizationUpdate(Update):

    def __init__(self, update_type, object_id, name=None, industry=None,
                 ticker=None, pricing_source=None, nonce=None):
        super(UpdateOrganizationUpdate, self).__init__(update_type)
        self._name = name
        self._industry = industry
        self._ticker = ticker
        self._pricing_source = pricing_source
        self._object_id = object_id
        self._nonce = nonce

    def check_valid(self, store, txn):
        if self._object_id not in store:
            raise InvalidTransactionError(
                "Object with id does not exist: {}".format(self._object_id))

        organization = store.get(self._object_id)
        try:
            participant = store.lookup('participant:key-id', txn.OriginatorID)
        except:
            raise InvalidTransactionError("Participant does not exist.")

        if participant["object-id"] != organization["creator-id"]:
            raise InvalidTransactionError(
                "Organization can only be updated by its creator {}"
                .format(participant["object-id"]))
        if self._name:
            try:
                store.lookup('organization:name', self._name)
                raise InvalidTransactionError(
                    "Object with name already exists: {}".format(self._name))
            except KeyError:
                pass

        if self._ticker is not None:
            if "ticker" in organization:
                raise InvalidTransactionError(
                    "Organization already has a ticker {}"
                    .format(self._ticker))
            try:
                store.lookup("organization:ticker", self.ticker)
                raise InvalidTransactionError(
                    "The ticker already exists {}".format(self._ticker))
            except KeyError:
                pass

        if self._pricing_source is not None:
            if "pricing-source" in organization:
                raise InvalidTransactionError(
                    "Organization already has a pricing source {}"
                    .format(self._pricing_source))
            try:
                store.lookup("organization:pricing-source",
                             self._pricing_source)
                raise InvalidTransactionError(
                    "The pricing source already exists {}"
                    .format(self._pricing_source))
            except KeyError:
                pass

            if len(self._pricing_source) != 4:
                raise InvalidTransactionError(
                    "Pricing source must be a four-character string: {}"
                    .format(self._pricing_source))

    def apply(self, store, txn):
        obj = store.lookup("organization:object-id", self._object_id)
        if self._name is not None:
            obj['name'] = self._name
        if self._industry is not None:
            obj['industry'] = self._industry
        if self._ticker is not None:
            obj['ticker'] = self._ticker
        if self._pricing_source is not None:
            obj['pricing-source'] = self._pricing_source

        store[self._object_id] = obj


class UpdateOrganizationAuthorizationUpdate(Update):
    def __init__(self, update_type, object_id, action, participant_id, role,
                 nonce=None):
        super(UpdateOrganizationAuthorizationUpdate,
              self).__init__(update_type)
        self._object_id = object_id
        self._action = action
        self._participant_id = participant_id
        self._role = role
        self._nonce = nonce

    def check_valid(self, store, txn):
        if self._object_id not in store:
            raise InvalidTransactionError(
                "Object with id does not exist: {}".format(self._object_id))

        organization = store.get(self._object_id)
        try:
            participant = store.lookup('participant:key-id', txn.OriginatorID)
        except:
            raise InvalidTransactionError("Participant does not exist.")

        if participant["object-id"] != self._participant_id:
            if participant["object-id"] != organization["creator-id"]:
                raise InvalidTransactionError("Only the creator of the "
                                              "organization, or the "
                                              "participant themselves, "
                                              "may remove or add a "
                                              "participant to the "
                                              "Authorization list")

        if self._action == "add":
            if "authorization" in organization:
                for participant in organization["authorization"]:
                    if self._participant_id == participant["participant-id"]:
                        raise InvalidTransactionError("Participant is "
                                                      "already in the "
                                                      "authorization list: {}"
                                                      .format(self.
                                                              _participant_id))

        is_in = False
        if self._action == "remove":
            if "authorization" in organization:
                for participant in organization["authorization"]:
                    if self._participant_id in participant["participant-id"]:
                        is_in = True
            if not is_in:
                raise InvalidTransactionError("Participant is not in the" +
                                              " authorization list")

        if self._role != "marketmaker" and self._role != "trader":
            raise InvalidTransactionError("Role must be either " +
                                          "marketmaker or trader: {}"
                                          .format(self._role))

    def apply(self, store, txn):
        obj = store.lookup("organization:object-id", self._object_id)
        if self._action == "add":
            if "authorization" in obj:
                participant = {"participant-id": self._participant_id,
                               "role": self._role}
                obj["authorization"] += [participant]
                obj["ref-count"] += 1
            else:
                participant = {"participant-id": self._participant_id,
                               "role": self._role}
                obj["authorization"] = [participant]
                obj["ref-count"] += 1

        else:
            participant_index = 0
            for i in range(len(obj["authorization"])):
                if obj["authorization"][i] == \
                        {"partipant-id": self._participant_id,
                         "role": self._role}:
                    participant_index = i
            del obj["authorization"][participant_index]
        store[self._object_id] = obj


class DeleteOrganizationUpdate(Update):
    def __init__(self, update_type, object_id, nonce=None):
        super(DeleteOrganizationUpdate, self).__init__(update_type)
        self._object_id = object_id
        self._nonce = nonce

    def check_valid(self, store, txn):
        if self._object_id not in store:
            raise InvalidTransactionError(
                "Object with id does not exist: {}".format(self._object_id))

        organization = store.get(self._object_id)
        try:
            participant = store.lookup('participant:key-id', txn.OriginatorID)
        except:
            raise InvalidTransactionError("Participant does not exist.")

        if participant["object-id"] != organization["creator-id"]:
            raise InvalidTransactionError(
                "Organization can only be deleted by its creator {}"
                .format(participant["object-id"]))

        if organization["ref-count"] != 0:
            raise InvalidTransactionError(
                "Organization can only be deleted if its ref-count is zero {}"
                .format(organization["ref-count"]))

    def apply(self, store, txn):
        store.delete(self._object_id)

        orglist_obj = store['organizations']
        orglist_obj['organization-list'].remove(self._object_id)
        store['organizations'] = orglist_obj


class CreateParticipantUpdate(Update):
    def __init__(self, update_type, username, firm_id=None, object_id=None,
                 nonce=None):
        super(CreateParticipantUpdate, self).__init__(update_type)
        self._username = username
        self._firm_id = firm_id
        self._nonce = nonce

        if object_id is None:
            self._object_id = self.create_id()
        else:
            self._object_id = object_id

    def check_valid(self, store, txn):
        if self._object_id in store:
            raise InvalidTransactionError(
                "Object with id already exists: {}".format(self._object_id))

        try:
            store.lookup('participant:username', self._username)
            raise InvalidTransactionError(
                "Username already exists: {}".format(self._username))
        except KeyError:
            pass

        if self._firm_id:
            try:
                store.get(self._firm_id, object_type='organization')
            except KeyError:
                raise InvalidTransactionError(
                    "Firm does not exist: {}".format(self._firm_id))

        if len(self._username) < 3 or len(self._username) > 16:
            raise InvalidTransactionError(
                "Usernames must be between 3 and 16 characters")

    def apply(self, store, txn):
        if self._firm_id:
            firm = store.get(self._firm_id)
            firm["ref-count"] += 1
            store[self._firm_id] = firm

        obj = {
            'object-type': 'participant',
            'username': self._username,
            'object-id': self._object_id,
            'creator-id': self._object_id,
            'key-id': txn.OriginatorID
        }
        if self._firm_id is not None:
            obj['firm-id'] = self._firm_id
        store[self._object_id] = obj


class UpdateParticipantUpdate(Update):
    def __init__(self, update_type, object_id, username=None, firm_id=None,
                 nonce=None):
        super(UpdateParticipantUpdate, self).__init__(update_type)
        self._object_id = object_id
        self._username = username
        self._firm_id = firm_id
        self._nonce = nonce

    def check_valid(self, store, txn):
        if self._object_id not in store:
            raise InvalidTransactionError(
                "Object does not exist {}".format(self._object_id))

        participant = store.lookup("participant:object-id", self._object_id)

        try:
            creator = store.lookup("participant:key-id", txn.OriginatorID)
        except KeyError:
            raise InvalidTransactionError(
                "Only the creator can update particpant")

        if creator["object-id"] != participant["creator-id"]:
            raise InvalidTransactionError(
                "Only the creator can update particpant")

        if self._username is not None:
            try:
                store.lookup('participant:username', self._username)
                raise InvalidTransactionError(
                    "Username already exists: {}".format(self._username))
            except KeyError:
                pass

        if self._firm_id is not None:
            try:
                store.lookup('organization:object-id', self._firm_id)
            except KeyError:
                raise InvalidTransactionError(
                    "Firm does not exist: {}".format(self._firm_id))

    def apply(self, store, txn):
        obj = store.lookup("participant:object-id", self._object_id)
        if self._firm_id is not None:
            if "firm-id" in obj:
                if self._firm_id != obj["firm-id"]:
                    old_firm_id = obj["firm-id"]
                    old_firm = store.get(old_firm_id)
                    old_firm["ref-count"] -= 1
                    store[old_firm_id] = old_firm
                    new_firm = store.get(self._firm_id)
                    new_firm["ref-count"] += 1
                    store[self._firm_id] = new_firm
            else:
                new_firm = store.get(self._firm_id)
                new_firm["ref-count"] += 1
                store[self._firm_id] = new_firm

        if self._username is not None:
            obj["username"] = self._username
        if self._firm_id is not None:
            obj["firm-id"] = self._firm_id
        store[self._object_id] = obj
