using System;
using System.Diagnostics.Contracts;
using Google.Protobuf;
using static Message.Types;

namespace Sawtooth.Sdk.Messaging
{
    public static class MessageExt
    {
        public static byte[] Encode(Message message, IMessage dataMessage, MessageType messageType)
        {
            var m = new Message(message);
            m.Content = dataMessage.ToByteString();
            m.MessageType = messageType;

            return m.ToByteString().ToByteArray();
        }

        public static Message Encode(IMessage dataMessage, MessageType messageType)
        {
            return new Message
            {
                Content = dataMessage.ToByteString(),
                MessageType = messageType,
                CorrelationId = Stream.GenerateId()
            };
        }

        public static T Decode<T>(Message message) 
            where T : IMessage, new()
        {
            var request = new T();
            request.MergeFrom(message.Content);
            return request;
        }
    }
}
