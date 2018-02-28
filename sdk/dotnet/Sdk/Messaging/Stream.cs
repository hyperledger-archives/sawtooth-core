using System;
using System.Collections.Concurrent;
using System.Diagnostics;
using System.Threading.Tasks;
using Google.Protobuf;
using NetMQ;
using NetMQ.Sockets;
using static Message.Types;
using System.Security.Cryptography;
using System.Text;
using System.Linq;
using System.Threading;

namespace Sawtooth.Sdk.Messaging
{
    public class Stream
    {
        readonly string Address;

        readonly NetMQSocket Socket;
        readonly NetMQPoller Poller;

        readonly ConcurrentDictionary<string, TaskCompletionSource<Message>> Futures;

        internal Func<TpProcessRequest, Task> ProcessRequestHandler;

        internal static SHA256 SHA256 = SHA256.Create();

        public Stream(string address)
        {
            Address = address;

            Socket = new DealerSocket();
            Socket.ReceiveReady += Receive;

            Poller = new NetMQPoller();
            Poller.Add(Socket);

            Futures = new ConcurrentDictionary<string, TaskCompletionSource<Message>>();
        }

        /// <summary>
        /// Generates a unique identifier
        /// </summary>
        /// <returns>The identifier.</returns>
        public static string GenerateId() => String.Concat(SHA256.ComputeHash(Guid.NewGuid().ToByteArray()).Select(x => x.ToString("x2")));

        void Receive(object _, NetMQSocketEventArgs e)
        {
            foreach (var frame in e.Socket.ReceiveMultipartBytes())
            {
                var message = new Message();
                message.MergeFrom(frame);

                switch (message.MessageType)
                {
                    case MessageType.PingRequest:
                        Socket.SendFrame(MessageExt.Encode(message, new PingResponse(), MessageType.PingResponse));
                        return;
                    case MessageType.TpProcessRequest:
                        Task.Run(async () =>
                        {
                            await ProcessRequestHandler?.Invoke(MessageExt.Decode<TpProcessRequest>(message))
                                .ContinueWith((task) =>
                                {
                                    if (task.Status == TaskStatus.RanToCompletion)
                                        Socket.SendFrame(MessageExt.Encode(message, new TpProcessResponse { Status = TpProcessResponse.Types.Status.Ok }, MessageType.TpProcessResponse));
                                    else
                                        Console.WriteLine("Couldn't complete handler Apply method.");
                                });
                        });
                        return;
                    case MessageType.TpRegisterResponse:
                        Console.WriteLine($"Transaction processor registration: {MessageExt.Decode<TpRegisterResponse>(message).Status}");
                        return;
                    default:
                        Debug.WriteLine($"Message of type {message.MessageType} received");
                        break;
                }

                if (Futures.TryGetValue(message.CorrelationId, out var source))
                {
                    if (source.Task.Status == TaskStatus.RanToCompletion)
                    {
                        source.SetResult(message);

                    }
                    Futures.TryRemove(message.CorrelationId, out var _);
                }
                else
                {
                    Debug.WriteLine("Possible unexpected message received");
                    Futures.TryAdd(message.CorrelationId, new TaskCompletionSource<Message>());
                }
            }
        }

        public void Disconnect()
        {
            Socket.Disconnect(Address);
            Poller.StopAsync();
        }

        public Task<Message> Send(Message message, CancellationToken cancellationToken)
        {
            var source = new TaskCompletionSource<Message>();
            cancellationToken.Register(() => source.SetCanceled());

            Futures.TryAdd(message.CorrelationId, source);

            Socket.SendFrame(message.ToByteString().ToByteArray());

            return source.Task;
        }

        public void Connect()
        {
            Socket.Connect(Address);
            Poller.RunAsync();
        }
    }
}
