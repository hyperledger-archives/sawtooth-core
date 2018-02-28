using System;
using System.Linq;
using System.Threading.Tasks;
using Google.Protobuf;
using NetMQ;
using NetMQ.Sockets;
using Sawtooth.Sdk.Messaging;
using Sawtooth.Sdk.Processor;
using Xunit;
using static Message.Types;

namespace Sawtooth.Sdk.Test
{
    public class ContextTests
    {
        [Fact]
        public async Task CanGetState()
        {
            var serverAddress = "inproc://get-state-test";

            var serverSocket = new PairSocket();
            serverSocket.Bind(serverAddress);

            var stream = new Stream(serverAddress);
            stream.Connect();

            var context = new Context(stream, "context");
            var addresses = new[] { "address1", "address2" };

            var task = Task.Run(() =>
            {
                var message = new Message();
                message.MergeFrom(serverSocket.ReceiveFrameBytes());

                Assert.Equal(MessageType.TpStateGetRequest, message.MessageType);

                var response = new TpStateGetResponse();
                response.Entries.AddRange(addresses.Select(x => new TpStateEntry { Address = x, Data = ByteString.Empty }));

                serverSocket.SendFrame(MessageExt.Encode(message, response, MessageType.TpStateGetResponse));
            });

            var stateResponse = await context.GetState(addresses);

            Assert.Equal(addresses.Length, stateResponse.Length);
        }
    }
}
