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
using Sawtooth.Sdk.Processor;
using Sawtooth.Sdk.Client;

namespace Sawtooth.Sdk.Messaging
{
    public class Stream
    {
        readonly string Address;

        readonly NetMQSocket Socket;
        readonly NetMQPoller Poller;

        readonly ConcurrentDictionary<string, TaskCompletionSource<Message>> Futures;

        public Func<TpProcessRequest, Task> ProcessRequestHandler;

        public Stream(string address)
        {
            Address = address;

            Socket = new DealerSocket();
            Socket.ReceiveReady += Receive;
            Socket.Options.ReconnectInterval = TimeSpan.FromSeconds(2);

            Poller = new NetMQPoller();
            Poller.Add(Socket);

            Futures = new ConcurrentDictionary<string, TaskCompletionSource<Message>>();
        }

        void Receive(object _, NetMQSocketEventArgs e)
        {
            var message = new Message();
            message.MergeFrom(Socket.ReceiveMultipartBytes().SelectMany(x => x).ToArray());

            switch (message.MessageType)
            {
                case MessageType.PingRequest:
                    Socket.SendFrame(new PingResponse().Wrap(message, MessageType.PingResponse).ToByteArray());
                    return;

                case MessageType.TpProcessRequest:
                    Task.Run(async () =>
                    {
                        await ProcessRequestHandler.Invoke(message.Unwrap<TpProcessRequest>())
                            .ContinueWith((task) =>
                            {
                                switch (task.Status)
                                {
                                    case TaskStatus.RanToCompletion:
                                        Socket.SendFrame(new TpProcessResponse { Status = TpProcessResponse.Types.Status.Ok }
                                                         .Wrap(message, MessageType.TpProcessResponse).ToByteArray());
                                        break;

                                    case TaskStatus.Faulted:
                                        var errorData = ByteString.CopyFrom(task.Exception?.ToString() ?? string.Empty, Encoding.UTF8);
                                        if (task.Exception != null && task.Exception.InnerException is InvalidTransactionException)
                                        {
                                            Socket.SendFrame(new TpProcessResponse { Status = TpProcessResponse.Types.Status.InvalidTransaction }
                                                             .Wrap(message, MessageType.TpProcessResponse).ToByteArray());
                                        }
                                        else
                                        {
                                            Socket.SendFrame(new TpProcessResponse { Status = TpProcessResponse.Types.Status.InternalError }
                                                           .Wrap(message, MessageType.TpProcessResponse).ToByteArray());
                                        }
                                        break;
                                }
                            });
                    });
                    return;

                case MessageType.TpUnregisterResponse:
                    Console.WriteLine($"Transaction processor unregister status: {message.Unwrap<TpUnregisterResponse>().Status}");
                    break;

                default:
                    Debug.WriteLine($"Message of type {message.MessageType} received");
                    break;
            }

            if (Futures.TryGetValue(message.CorrelationId, out var source))
            {
                if (source.Task.Status != TaskStatus.RanToCompletion) source.SetResult(message);
                Futures.TryRemove(message.CorrelationId, out var _);
            }
            else
            {
                Debug.WriteLine("Possible unexpected message received");
                Futures.TryAdd(message.CorrelationId, new TaskCompletionSource<Message>());
            }
        }

        public Task<Message> Send(Message message, CancellationToken cancellationToken)
        {
            var source = new TaskCompletionSource<Message>();
            cancellationToken.Register(() => source.SetCanceled());

            if (Futures.TryAdd(message.CorrelationId, source))
            {
                Socket.SendFrame(message.ToByteString().ToByteArray());
                return source.Task;
            }
            if (Futures.TryGetValue(message.CorrelationId, out var task))
            {
                return task.Task;
            }
            throw new InvalidOperationException("Cannot get or set future context for this message.");
        }

        public void Connect()
        {
            if (ProcessRequestHandler == null)
                throw new ArgumentNullException(nameof(ProcessRequestHandler), "Process request handler must be set");
            
            Socket.Connect(Address);
            Poller.RunAsync();
        }

        public void Disconnect()
        {
            Socket.Disconnect(Address);
            Poller.StopAsync();
        }
    }
}
