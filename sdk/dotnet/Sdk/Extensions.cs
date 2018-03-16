using System;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using Google.Protobuf;
using static Message.Types;

namespace Sawtooth.Sdk
{
    public static class Extensions
    {
        public static Message Wrap(this IMessage message, Message requestMessage, MessageType messageType)
        {
            return new Message
            {
                MessageType = messageType,
                CorrelationId = requestMessage.CorrelationId,
                Content = message.ToByteString()
            };
        }

        public static Message Wrap(this IMessage message, MessageType messageType)
        {
            return new Message
            {
                MessageType = messageType,
                CorrelationId = Guid.NewGuid().ToByteArray().ToSha256().ToHexString(),
                Content = message.ToByteString()
            };
        }

        public static T Unwrap<T>(this Message message)
            where T : IMessage, new()
        {
            var request = new T();
            request.MergeFrom(message.Content);
            return request;
        }

        public static string ToHexString(this byte[] data) => String.Concat(data.Select(x => x.ToString("x2")));

        public static byte[] ToSha256(this byte[] data) => SHA256.Create().ComputeHash(data);

        public static byte[] ToSha512(this byte[] data) => SHA512.Create().ComputeHash(data);

        public static byte[] ToByteArray(this string data) => Encoding.UTF8.GetBytes(data);
    }
}
