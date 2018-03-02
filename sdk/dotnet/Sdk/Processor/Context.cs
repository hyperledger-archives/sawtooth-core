using System;
using System.Collections.Generic;
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

        public async Task<Dictionary<string, ByteString>> GetState(string[] addresses)
        {
            var request = new TpStateGetRequest { ContextId = ContextId };
            request.Addresses.AddRange(addresses);

            return MessageExt.Decode<TpStateGetResponse>(
                await Stream.Send(MessageExt.Encode(request, MessageType.TpStateGetRequest), CancellationToken.None))
                             .Entries.ToDictionary(x => x.Address, x => x.Data);
        }

        public async Task<string[]> SetState(Dictionary<string, ByteString> addressValuePairs)
        {
            var request = new TpStateSetRequest { ContextId = ContextId };
            request.Entries.AddRange(addressValuePairs.Select(x => new TpStateEntry { Address = x.Key, Data = x.Value }));

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

        public async Task<bool> AddReceiptData(ByteString data)
        {
            var request = new TpReceiptAddDataRequest() { ContextId = ContextId };
            request.Data = data;

            return MessageExt.Decode<TpReceiptAddDataResponse>(
                await Stream.Send(MessageExt.Encode(request, MessageType.TpReceiptAddDataRequest), CancellationToken.None))
                             .Status == TpReceiptAddDataResponse.Types.Status.Ok;
        }
    }
}
