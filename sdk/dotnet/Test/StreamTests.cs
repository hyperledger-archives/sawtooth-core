using System;
using System.Threading.Tasks;
using Google.Protobuf;
using NetMQ;
using NetMQ.Sockets;
using Sawtooth.Sdk.Messaging;
using Xunit;
using static Message.Types;

namespace Sawtooth.Sdk.Test
{
    public class StreamTests
    {
        [Fact]
        public void RespondToPing()
        {
            // Setup
            var serverSocket = new PairSocket();
            serverSocket.Bind("inproc://stream-test");

            var pingMessage = new PingRequest().Wrap(MessageType.PingRequest);

            var stream = new Stream("inproc://stream-test");
            stream.ProcessRequestHandler = delegate { return Task.CompletedTask; }; // setting empty handler, to avoid exception
            stream.Connect();

            // Run test case
            var task1 = Task.Run(() => serverSocket.SendFrame(pingMessage.ToByteString().ToByteArray()));
            var task2 = Task.Run(() =>
            {
                var message = new Message();
                message.MergeFrom(serverSocket.ReceiveFrameBytes());

                return message;
            });

            Task.WhenAll(new[] { task1, task2 });

            var actualMessage = task2.Result;

            // Verify
            Assert.Equal(MessageType.PingResponse, actualMessage.MessageType);
            Assert.Equal(pingMessage.CorrelationId, actualMessage.CorrelationId);

            serverSocket.Unbind("inproc://stream-test");
            stream.Disconnect();
        }
    }
}
