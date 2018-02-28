using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Google.Protobuf;
using Sawtooth.Sdk.Messaging;
using static Message.Types;

namespace Sawtooth.Sdk.Processor
{
    public class TransactionProcessor
    {
        readonly Stream Stream;

        readonly List<ITransactionHandler> Handlers = new List<ITransactionHandler>();

        public TransactionProcessor(string address)
        {
            Stream = new Stream(address);
            Stream.ProcessRequestHandler = OnProcessRequest;
        }

        public void AddHandler(ITransactionHandler handler) => Handlers.Add(handler);

        public async Task Start()
        {
            Stream.Connect();

            foreach (var handler in Handlers)
            {
                var request = new TpRegisterRequest { Version = handler.Version, Family = handler.FamilyName };
                request.Namespaces.AddRange(handler.Namespaces);

                var registrationResult = MessageExt.Decode<TpRegisterResponse>(await Stream.Send(MessageExt.Encode(request, MessageType.TpRegisterRequest), CancellationToken.None));

                Debug.WriteLine($"Transaction processor {handler.FamilyName} {handler.Version} registration status: {registrationResult.Status}");
            }
        }

        async Task OnProcessRequest(TpProcessRequest request)
        {
            await Handlers.FirstOrDefault(x => x.FamilyName == request.Header.FamilyName 
                                          && x.Version == request.Header.FamilyVersion)?
                          .Apply(request, new Context(Stream, request.ContextId));
        }
    }
}
