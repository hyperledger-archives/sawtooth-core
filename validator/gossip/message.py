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
This module defines the Packet and Message classes, which are responsible
for representing data transmissions in the gossip protocol.
"""

import logging
import struct
import time

from gossip.common import cbor2dict, dict2cbor
from gossip.signed_object import SignedObject

logger = logging.getLogger(__name__)


class Packet(object):
    """The Packet class manages the data that goes onto and comes off of
    the wire.

    Attributes:
        PackedFormat (str): A struct packed format string representing
            the packed structure of the header.
        TimeToLive (int): The maximum number of hops to forward the
            message.
        SequenceNumber (int): A monotonically increasing counter used to
            identify packets.
        IsAcknowledgement (bool): Whether this packet is an
            acknowledgement packet.
        IsReliable (bool): Whether this packet uses reliable delivery.
        SenderID (str): The identifier for the node that sent this
            packet.
        Data (str): The data content of the packet.
        TransmitTime (float): The time the packet was transmitted, in
            seconds since the epoch.
        RoundTripEstimate (float): An estimate of the round trip time
            to send a message and receive a response.
        DestinationID (str): The identifier for the node that is
            intended to receive this packet.
        Identifier (str): The message identifier.
    """

    PackedFormat = '!LL??36s'

    def __init__(self):
        """Constructor for the Packet class.
        """
        self.TimeToLive = 255
        self.SequenceNumber = 0
        self.IsAcknowledgement = False
        self.IsReliable = True
        self.SenderID = '========================'

        self.Message = None
        self.Data = ''

        # bookkeeping properties
        self.TransmitTime = 0.0
        self.RoundTripEstimate = 0.0
        self.DestinationID = '========================'
        self.Identifier = None

    def __str__(self):
        return "PKT:{0}:{1}".format(self.SenderID[:8], self.SequenceNumber)

    def create_ack(self, sender):
        """Creates a new Packet instance with IsAcknowledgement == True
        and a sequence number which matches this Packet.

        Args:
            sender (str): An identifier for the sending node.

        Returns:
            Packet: An acknowledgement Packet associated with this Packet.
        """
        packet = Packet()

        packet.TimeToLive = 0
        packet.SequenceNumber = self.SequenceNumber
        packet.IsAcknowledgement = True
        packet.IsReliable = False
        packet.SenderID = sender

        packet.Data = ''

        return packet

    def add_message(self, msg, src, dst, seqno):
        """Resets the Packet with the attributes of the Message.

        Args:
            msg (message.Message): The message to apply to the packet.
            src (Node): The source node of the packet.
            dst (Node): The destination node of the packet.
            seqno (int): The sequence number of the packet.
        """
        self.IsAcknowledgement = False

        self.Identifier = msg.Identifier
        self.TimeToLive = msg.TimeToLive
        self.IsReliable = msg.IsReliable
        self.SequenceNumber = seqno

        self.SenderID = src.Identifier
        self.DestinationID = dst.Identifier
        self.RoundTripEstimate = dst.Estimator.RTO

        self.Message = msg
        self.Data = repr(msg)

    def unpack(self, databuf):
        """Resets the Packet with the contents of a packed object.

        Args:
            databuf (bytes): A packed object with a header conforming
                to PackedFormat.
        """
        size = struct.calcsize(self.PackedFormat)

        (ttl, seqno, aflag, rflag, senderid) = struct.unpack(self.PackedFormat,
                                                             databuf[:size])

        self.TimeToLive = ttl
        self.SequenceNumber = int(seqno)
        self.IsAcknowledgement = aflag
        self.IsReliable = rflag
        self.SenderID = senderid.rstrip('\0')

        self.Data = databuf[size:]

    def pack(self):
        """Builds a packed object with a header conforming to PackedFormat
        and includes body contents.

        Returns:
            bytes: A packed object with a header conforming to
                PackedFormat.
        """
        header = struct.pack(self.PackedFormat, self.TimeToLive,
                             self.SequenceNumber, self.IsAcknowledgement,
                             self.IsReliable, str(self.SenderID))

        return header + self.Data


def unpack_message_data(data):
    """Unpacks CBOR encoded data into a dict.

    Args:
        data (bytes): CBOR encoded data.

    Returns:
        dict: A dict reflecting the contents of the CBOR encoded
            representation.
    """
    return cbor2dict(data)


class Message(SignedObject):
    """A Message contains the information and metadata to be transmitted to
    a node.

    Attributes:
        Message.MessageType (str): The class name of the message.
        DefaultTimeToLive (int): The default number of hops that the
            message is considered alive.
        Nonce (float): A locally unique value generated by the message
            sender.
        SenderID (str): Identifier for the node that sent the packet in
            which the message was delivered. The SenderID is the peer node
            in the gossip network.
        IsSystemMessage (bool): Whether or not this is a system message.
            System messages have special delivery priority rules.
        IsForward (bool): Whether the message should be automatically
            forwarded.
        IsReliable (bool): Whether reliable delivery is required.
        TimeToLive (int): The configured number of hops that the message
            is considered alive.
    """
    MessageType = "/gossip.Message/MessageBase"
    DefaultTimeToLive = 2 ** 31

    def __init__(self, minfo=None):
        """Constructor for the Message class.

        Args:
            minfo (dict): dictionary of values for message fields,
                generally created from a call to dump().
        """
        if minfo is None:
            minfo = {}
        super(Message, self).__init__(minfo, sig_dict_key='__SIGNATURE__')

        self.Nonce = minfo.get('__NONCE__', time.time())

        self.SenderID = '========================'

        self.IsSystemMessage = False
        self.IsForward = True
        self.IsReliable = True

        self.TimeToLive = self.DefaultTimeToLive

        self._data = None

    def __str__(self):
        return "MSG:{0}:{1}".format(self.OriginatorID[:8], self.Identifier[:8])

    def __repr__(self):
        if not self._data:
            self._data = self.serialize()
        return self._data

    def __len__(self):
        if not self._data:
            self._data = dict2cbor(self.dump())
        return len(self._data)

    def dump(self):
        """Builds a dict containing base object key/values and message type
        and nonce.

        Returns:
            dict: a mapping containing information about the message.
        """
        result = super(Message, self).dump()

        result['__TYPE__'] = self.MessageType
        result['__NONCE__'] = self.Nonce

        return result
