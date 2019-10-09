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
import os
import time

from urllib.parse import urlparse

from sawtooth_signing import create_context
from sawtooth_signing import ParseError
from sawtooth_signing.secp256k1 import Secp256k1PublicKey

import netifaces

from sawtooth_validator.networking.dispatch import Handler
from sawtooth_validator.networking.dispatch import HandlerResult
from sawtooth_validator.networking.dispatch import HandlerStatus
from sawtooth_validator.networking.interconnect import ConnectionStatus
from sawtooth_validator.networking.interconnect import AuthorizationType
from sawtooth_validator.protobuf import validator_pb2
from sawtooth_validator.protobuf.authorization_pb2 import ConnectionRequest
from sawtooth_validator.protobuf.authorization_pb2 import ConnectionResponse
from sawtooth_validator.protobuf.authorization_pb2 import \
    AuthorizationTrustRequest
from sawtooth_validator.protobuf.authorization_pb2 import \
    AuthorizationTrustResponse
from sawtooth_validator.protobuf.authorization_pb2 import \
    AuthorizationChallengeResponse
from sawtooth_validator.protobuf.authorization_pb2 import \
    AuthorizationChallengeSubmit
from sawtooth_validator.protobuf.authorization_pb2 import \
    AuthorizationChallengeResult
from sawtooth_validator.protobuf.authorization_pb2 import \
    AuthorizationViolation
from sawtooth_validator.protobuf.authorization_pb2 import RoleType
from sawtooth_validator.protobuf.network_pb2 import NetworkAcknowledgement
from sawtooth_validator.protobuf.network_pb2 import DisconnectMessage
from sawtooth_validator.protobuf.network_pb2 import PingRequest
from sawtooth_validator.protobuf.network_pb2 import PingResponse
from sawtooth_validator.journal.timed_cache import TimedCache


LOGGER = logging.getLogger(__name__)
PAYLOAD_LENGTH = 64
AUTHORIZATION_CACHE_TIMEOUT = 300


class ConnectHandler(Handler):
    def __init__(self, network):
        self._network = network

    @staticmethod
    def is_valid_endpoint_host(interfaces, endpoint):
        """
        An endpoint host name is valid if it is a URL and if the
        host is not the name of a network interface.
        """
        result = urlparse(endpoint)
        hostname = result.hostname
        if hostname is None:
            return False

        for interface in interfaces:
            if interface == hostname:
                return False

        return True

    def handle(self, connection_id, message_content):
        """
        A connection must use one of the supported authorization types
        to prove their identity. If a requester deviates
        from the procedure in any way, the requester will be rejected and the
        connection will be closed. The same is true if the requester sends
        multiple ConnectionRequests or multiple of any authorization-type
        message. The validator receiving a new connection will receive a
        ConnectionRequest. The validator will respond with a ConnectionResponse
        message. The ConnectionResponse message will contain a list of
        RoleEntry messages and an AuthorizationType. Role entries are
        the accepted type of connections that are supported on the endpoint
        that the ConnectionRequest was sent to. AuthorizationType describes the
        procedure required to gain access to that role. If the validator is not
        accepting connections or does not support the listed authorization
        type, return an ConnectionResponse.ERROR and close the connection.
        """
        message = ConnectionRequest()
        message.ParseFromString(message_content)
        LOGGER.debug("got connect message from %s. sending ack", connection_id)

        # Need to use join here to get the string "0.0.0.0". Otherwise,
        # bandit thinks we are binding to all interfaces and returns a
        # Medium security risk.
        interfaces = ["*", ".".join(["0", "0", "0", "0"])]
        interfaces += netifaces.interfaces()
        if self.is_valid_endpoint_host(interfaces, message.endpoint) is False:
            LOGGER.warning("Connecting peer provided an invalid endpoint: %s; "
                           "Ignoring connection request.",
                           message.endpoint)
            connection_response = ConnectionResponse(
                status=ConnectionResponse.ERROR)
            return HandlerResult(
                HandlerStatus.RETURN_AND_CLOSE,
                message_out=connection_response,
                message_type=validator_pb2.Message.
                AUTHORIZATION_CONNECTION_RESPONSE)

        LOGGER.debug("Endpoint of connecting node is %s", message.endpoint)
        self._network.update_connection_endpoint(connection_id,
                                                 message.endpoint)

        # Get what AuthorizationType the network role requires
        roles = self._network.roles
        auth_type = roles.get("network")
        if auth_type == AuthorizationType.TRUST:
            role_type = ConnectionResponse.RoleEntry(
                role=RoleType.Value("NETWORK"),
                auth_type=ConnectionResponse.TRUST)
            connection_response = ConnectionResponse(roles=[role_type])
        elif auth_type == AuthorizationType.CHALLENGE:
            role_type = ConnectionResponse.RoleEntry(
                role=RoleType.Value("NETWORK"),
                auth_type=ConnectionResponse.CHALLENGE)
            connection_response = ConnectionResponse(roles=[role_type])
        else:
            LOGGER.warning("Network role is set to an unsupported"
                           "Authorization Type: %s", auth_type)
            connection_response = ConnectionResponse(
                status=ConnectionResponse.ERROR)
            return HandlerResult(
                HandlerStatus.RETURN_AND_CLOSE,
                message_out=connection_response,
                message_type=validator_pb2.Message.
                AUTHORIZATION_CONNECTION_RESPONSE)

        try:
            is_outbound_connection = self._network.is_outbound_connection(
                connection_id)
        except KeyError:
            # Connection has gone away, drop message
            return HandlerResult(HandlerStatus.DROP)

        if not is_outbound_connection:
            if self._network.allow_inbound_connection():
                LOGGER.debug("Allowing incoming connection: %s", connection_id)
                connection_response.status = connection_response.OK
            else:
                connection_response.status = connection_response.ERROR
                return HandlerResult(
                    HandlerStatus.RETURN_AND_CLOSE,
                    message_out=connection_response,
                    message_type=validator_pb2.Message.
                    AUTHORIZATION_CONNECTION_RESPONSE)

        if self._network.get_connection_status(connection_id) is not None:
            LOGGER.debug("Connection has already sent ConnectionRequest:"
                         " %s, Remove connection.", connection_id)
            connection_response.status = connection_response.ERROR
            return HandlerResult(
                HandlerStatus.RETURN_AND_CLOSE,
                message_out=connection_response,
                message_type=validator_pb2.Message.
                AUTHORIZATION_CONNECTION_RESPONSE)

        self._network.update_connection_status(
            connection_id,
            ConnectionStatus.CONNECTION_REQUEST)

        return HandlerResult(
            HandlerStatus.RETURN,
            message_out=connection_response,
            message_type=validator_pb2.Message.
            AUTHORIZATION_CONNECTION_RESPONSE)


class DisconnectHandler(Handler):
    def __init__(self, network):
        self._network = network

    def handle(self, connection_id, message_content):
        message = DisconnectMessage()
        message.ParseFromString(message_content)
        LOGGER.debug("got disconnect message from %s. sending ack",
                     connection_id)

        ack = NetworkAcknowledgement()
        ack.status = ack.OK
        self._network.remove_connection(connection_id)

        return HandlerResult(
            HandlerStatus.RETURN,
            message_out=ack,
            message_type=validator_pb2.Message.NETWORK_ACK)


class PingRequestHandler(Handler):
    def __init__(self, network, allowed_frequency=10):
        self._network = network
        self._last_message = TimedCache()
        self._allowed_frequency = allowed_frequency

    def handle(self, connection_id, message_content):

        request = PingRequest()
        request.ParseFromString(message_content)

        ack = PingResponse()
        if self._network.get_connection_status(connection_id) == \
                ConnectionStatus.CONNECTED:

            if connection_id in self._last_message:
                del self._last_message[connection_id]

            return HandlerResult(
                HandlerStatus.RETURN,
                message_out=ack,
                message_type=validator_pb2.Message.PING_RESPONSE)

        if connection_id in self._last_message:
            ping_frequency = time.time() - self._last_message[connection_id]

            if ping_frequency < self._allowed_frequency:
                LOGGER.warning("Too many Pings (%s) in %s seconds before "
                               "authorization is complete: %s",
                               ping_frequency,
                               self._allowed_frequency,
                               connection_id)
                violation = AuthorizationViolation(
                    violation=RoleType.Value("NETWORK"))

                return HandlerResult(
                    HandlerStatus.RETURN_AND_CLOSE,
                    message_out=violation,
                    message_type=validator_pb2.Message.AUTHORIZATION_VIOLATION)

        self._last_message[connection_id] = time.time()

        return HandlerResult(
            HandlerStatus.RETURN,
            message_out=ack,
            message_type=validator_pb2.Message.PING_RESPONSE)


class PingResponseHandler(Handler):
    def __init__(self):
        pass

    def handle(self, connection_id, message_content):
        """
        If a PingResponse is received and there is not a future to resolve, the
        message is dropped. Interconnect will have already updated the last
        message time for the connection.
        """
        return HandlerResult(HandlerStatus.DROP)


class AuthorizationTrustRequestHandler(Handler):
    def __init__(self, network, permission_verifier, gossip):
        self._network = network
        self._permission_verifier = permission_verifier
        self._gossip = gossip

    def handle(self, connection_id, message_content):
        """
        The simplest authorization type will be Trust. If Trust authorization
        is enabled, the validator will trust the connection and approve any
        roles requested that are available on that endpoint. If the requester
        wishes to gain access to every role it has permission to access, it can
        request access to the role ALL, and the validator will respond with all
        available roles. If the permission verifier deems the connection to not
        have access to a role, the connection has not sent a ConnectionRequest
        or a the connection has already recieved a AuthorizationTrustResponse,
        an AuthorizatinViolation will be returned and the connection will be
        closed.
        """
        if self._network.get_connection_status(connection_id) != \
                ConnectionStatus.CONNECTION_REQUEST:
            LOGGER.debug("Connection's previous message was not a"
                         " ConnectionRequest, Remove connection to %s",
                         connection_id)
            violation = AuthorizationViolation(
                violation=RoleType.Value("NETWORK"))
            return HandlerResult(
                HandlerStatus.RETURN_AND_CLOSE,
                message_out=violation,
                message_type=validator_pb2.Message
                .AUTHORIZATION_VIOLATION)

        request = AuthorizationTrustRequest()
        request.ParseFromString(message_content)

        # Check that the connection's public key is allowed by the network role
        roles = self._network.roles
        for role in request.roles:
            if role == RoleType.Value("NETWORK") or role == \
                    RoleType.Value("ALL"):
                permitted = False
                if "network" in roles:
                    permitted = self._permission_verifier.check_network_role(
                        request.public_key)
                if not permitted:
                    violation = AuthorizationViolation(
                        violation=RoleType.Value("NETWORK"))
                    return HandlerResult(
                        HandlerStatus.RETURN_AND_CLOSE,
                        message_out=violation,
                        message_type=validator_pb2.Message
                        .AUTHORIZATION_VIOLATION)

        self._network.update_connection_public_key(connection_id,
                                                   request.public_key)

        if RoleType.Value("NETWORK") in request.roles:
            # Need to send ConnectionRequest to authorize ourself with the
            # connection if they initialized the connection
            try:
                is_outbound_connection = self._network.is_outbound_connection(
                    connection_id)
            except KeyError:
                # Connection has gone away, drop message
                return HandlerResult(HandlerStatus.DROP)

            if not is_outbound_connection:
                self._network.send_connect_request(connection_id)
            else:
                # If this is an outbound connection, authorization is complete
                # for both connections and peering can begin.
                self._gossip.connect_success(connection_id)

        auth_trust_response = AuthorizationTrustResponse(
            roles=[RoleType.Value("NETWORK")])

        LOGGER.debug("Connection: %s is approved", connection_id)

        self._network.update_connection_status(
            connection_id,
            ConnectionStatus.CONNECTED)

        return HandlerResult(
            HandlerStatus.RETURN,
            message_out=auth_trust_response,
            message_type=validator_pb2.Message.AUTHORIZATION_TRUST_RESPONSE)


class AuthorizationChallengeRequestHandler(Handler):
    def __init__(self, network):
        self._network = network
        self._challenge_payload_cache = TimedCache(
            keep_time=AUTHORIZATION_CACHE_TIMEOUT)

    def get_challenge_payload_cache(self):
        return self._challenge_payload_cache

    def handle(self, connection_id, message_content):
        """
        If the connection wants to take on a role that requires a challenge to
        be signed, it will request the challenge by sending an
        AuthorizationChallengeRequest to the validator it wishes to connect to.
        The validator will send back a random payload that must be signed.
        If the connection has not sent a ConnectionRequest or the connection
        has already recieved an AuthorizationChallengeResponse, an
        AuthorizationViolation will be returned and the connection will be
        closed.
        """
        if self._network.get_connection_status(connection_id) != \
                ConnectionStatus.CONNECTION_REQUEST:
            LOGGER.debug("Connection's previous message was not a"
                         " ConnectionRequest, Remove connection to %s",
                         connection_id)
            violation = AuthorizationViolation(
                violation=RoleType.Value("NETWORK"))
            return HandlerResult(
                HandlerStatus.RETURN_AND_CLOSE,
                message_out=violation,
                message_type=validator_pb2.Message
                .AUTHORIZATION_VIOLATION)

        random_payload = os.urandom(PAYLOAD_LENGTH)
        self._challenge_payload_cache[connection_id] = random_payload
        auth_challenge_response = AuthorizationChallengeResponse(
            payload=random_payload)

        self._network.update_connection_status(
            connection_id,
            ConnectionStatus.AUTH_CHALLENGE_REQUEST)

        return HandlerResult(
            HandlerStatus.RETURN,
            message_out=auth_challenge_response,
            message_type=validator_pb2.Message.
            AUTHORIZATION_CHALLENGE_RESPONSE)


class AuthorizationChallengeSubmitHandler(Handler):
    def __init__(self, network, permission_verifier, gossip, cache):
        self._network = network
        self._permission_verifier = permission_verifier
        self._gossip = gossip
        self._challenge_payload_cache = cache

    @staticmethod
    def _network_violation_result():
        violation = AuthorizationViolation(
            violation=RoleType.Value("NETWORK"))
        return HandlerResult(
            HandlerStatus.RETURN_AND_CLOSE,
            message_out=violation,
            message_type=validator_pb2.Message.AUTHORIZATION_VIOLATION)

    def handle(self, connection_id, message_content):
        """
        When the validator receives an AuthorizationChallengeSubmit message, it
        will verify the public key against the signature. If the public key is
        verified, the requested roles will be checked against the stored roles
        to see if the public key is included in the policy. If the node’s
        response is accepted, the node’s public key will be stored and the
        requester may start sending messages for the approved roles.

        If the requester wanted a role that is either not available on the
        endpoint, the requester does not have access to one of the roles
        requested, or the previous message was not an
        AuthorizationChallengeRequest, the challenge will be rejected and the
        connection will be closed.
        """
        if self._network.get_connection_status(connection_id) != \
                ConnectionStatus.AUTH_CHALLENGE_REQUEST:
            LOGGER.debug("Connection's previous message was not a"
                         " AuthorizationChallengeRequest, Remove connection to"
                         "%s",
                         connection_id)
            return AuthorizationChallengeSubmitHandler \
                ._network_violation_result()

        auth_challenge_submit = AuthorizationChallengeSubmit()
        auth_challenge_submit.ParseFromString(message_content)

        try:
            payload = self._challenge_payload_cache[connection_id]
        except KeyError:
            LOGGER.warning("Connection's challenge payload expired before a"
                           "response was received. %s", connection_id)
            return AuthorizationChallengeSubmitHandler \
                ._network_violation_result()

        context = create_context('secp256k1')
        try:
            public_key = Secp256k1PublicKey.from_hex(
                auth_challenge_submit.public_key)
        except ParseError:
            LOGGER.warning('Authorization Challenge Request cannot be '
                           'verified. Invalid public key %s',
                           auth_challenge_submit.public_key)
            return AuthorizationChallengeSubmitHandler \
                ._network_violation_result()

        if not context.verify(auth_challenge_submit.signature,
                              payload,
                              public_key):
            LOGGER.warning("Signature was not able to be verified. Remove "
                           "connection to %s", connection_id)
            return AuthorizationChallengeSubmitHandler \
                ._network_violation_result()

        roles = self._network.roles
        for role in auth_challenge_submit.roles:
            if role == RoleType.Value("NETWORK") or role == \
                    RoleType.Value("ALL"):
                permitted = False
                if "network" in roles:
                    permitted = self._permission_verifier.check_network_role(
                        auth_challenge_submit.public_key)
                if not permitted:
                    return AuthorizationChallengeSubmitHandler \
                        ._network_violation_result()

        self._network.update_connection_public_key(
            connection_id,
            auth_challenge_submit.public_key)

        if RoleType.Value("NETWORK") in auth_challenge_submit.roles:
            # Need to send ConnectionRequest to authorize ourself with the
            # connection if they initialized the connection
            try:
                is_outbound_connection = self._network.is_outbound_connection(
                    connection_id)
            except KeyError:
                # Connection has gone away, drop message
                return HandlerResult(HandlerStatus.DROP)

            if not is_outbound_connection:
                self._network.send_connect_request(connection_id)
            else:
                # If this is an outbound connection, authorization is complete
                # for both connections and peering/topology build out can
                # begin.
                self._gossip.connect_success(connection_id)

        auth_challenge_result = AuthorizationChallengeResult(
            roles=[RoleType.Value("NETWORK")])

        LOGGER.debug("Connection: %s is approved", connection_id)
        self._network.update_connection_status(
            connection_id,
            ConnectionStatus.CONNECTED)
        return HandlerResult(
            HandlerStatus.RETURN,
            message_out=auth_challenge_result,
            message_type=validator_pb2.Message.AUTHORIZATION_CHALLENGE_RESULT)


class AuthorizationViolationHandler(Handler):
    def __init__(self, network, gossip):
        self._network = network
        self._gossip = gossip

    def handle(self, connection_id, message_content):
        """
        If an AuthorizationViolation is recieved, the connection has decided
        that this validator is no longer permitted to be connected.
        Remove the connection preemptively.
        """
        LOGGER.warning("Received AuthorizationViolation from %s",
                       connection_id)
        # Close the connection
        endpoint = self._network.connection_id_to_endpoint(connection_id)
        self._network.remove_connection(connection_id)
        self._gossip.remove_temp_endpoint(endpoint)
        return HandlerResult(HandlerStatus.DROP)
