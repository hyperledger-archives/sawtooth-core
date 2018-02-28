using System;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Google.Protobuf;
using Google.Protobuf.Collections;
using Sawtooth.Sdk.Messaging;
using static Message.Types;

namespace Sawtooth.Sdk.Processor
{
    public class Context
    {
        readonly Stream Stream;
        readonly string ContextId;

        public Context(Stream stream, string contextId)
        {
            Stream = stream;
            ContextId = contextId;
        }

        public async Task<TpStateEntry[]> GetState(string[] addresses)
        {
            var request = new TpStateGetRequest { ContextId = ContextId };
            request.Addresses.AddRange(addresses);

            return MessageExt.Decode<TpStateGetResponse>(
                await Stream.Send(MessageExt.Encode(request, MessageType.TpStateGetRequest), CancellationToken.None))
                             .Entries.ToArray();
        }

        public async Task<string[]> SetState(TpStateEntry[] addressValuePairs)
        {
            var request = new TpStateSetRequest { ContextId = ContextId };
            request.Entries.AddRange(addressValuePairs);

            return MessageExt.Decode<TpStateSetResponse>(
                await Stream.Send(MessageExt.Encode(request, MessageType.TpStateSetRequest), CancellationToken.None))
                             .Addresses.ToArray();
        }

        public async Task<string[]> DeleteState(string[] addresses)
        {
            var request = new TpStateDeleteRequest { ContextId = ContextId };
            request.Addresses.AddRange(addresses);

            return MessageExt.Decode<TpStateDeleteResponse>(
                await Stream.Send(MessageExt.Encode(request, MessageType.TpStateDeleteRequest), CancellationToken.None))
                             .Addresses.ToArray();
        }

        public async Task<TpReceiptAddDataResponse.Types.Status> AddReceiptData(ByteString data)
        {
            var request = new TpReceiptAddDataRequest() { ContextId = ContextId };
            request.Data = data;

            return MessageExt.Decode<TpReceiptAddDataResponse>(
                await Stream.Send(MessageExt.Encode(request, MessageType.TpReceiptAddDataRequest), CancellationToken.None))
                             .Status;
        }
    }
}
