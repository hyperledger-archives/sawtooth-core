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
    AuthorizationViolation
from sawtooth_validator.protobuf.authorization_pb2 import RoleType
from sawtooth_validator.protobuf.network_pb2 import NetworkAcknowledgement
from sawtooth_validator.protobuf.network_pb2 import DisconnectMessage
from sawtooth_validator.protobuf.network_pb2 import PingRequest


LOGGER = logging.getLogger(__name__)


class ConnectHandler(Handler):
    def __init__(self, network):
        self._network = network

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
        LOGGER.debug("got connect message from %s. sending ack",
                     connection_id)
        LOGGER.debug("Endpoint of connecting node is %s",
                     message.endpoint)
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

        if not self._network.is_outbound_connection(connection_id):
            if self._network.allow_inbound_connection():
                LOGGER.debug("Allowing incoming connection: %s",
                             connection_id)
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


class PingHandler(Handler):

    def handle(self, connection_id, message_content):
        request = PingRequest()
        request.ParseFromString(message_content)

        ack = NetworkAcknowledgement()
        ack.status = ack.OK

        return HandlerResult(
            HandlerStatus.RETURN,
            message_out=ack,
            message_type=validator_pb2.Message.NETWORK_ACK)


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
            LOGGER.debug("Connection has previous message was not a"
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
            if not self._network.is_outbound_connection(connection_id):
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
        #
        self._gossip.remove_temp_endpoint(endpoint)
        return HandlerResult(HandlerStatus.DROP)
