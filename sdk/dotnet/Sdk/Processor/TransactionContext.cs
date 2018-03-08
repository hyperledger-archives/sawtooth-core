using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Google.Protobuf;
using Sawtooth.Sdk.Messaging;
using static Message.Types;

namespace Sawtooth.Sdk.Processor
{
    public class TransactionContext
    {
        readonly Stream Stream;
        readonly string ContextId;

        public TransactionContext(Stream stream, string contextId)
        {
            Stream = stream;
            ContextId = contextId;
        }

        public async Task<Dictionary<string, ByteString>> GetStateAsync(string[] addresses)
        {
            var request = new TpStateGetRequest { ContextId = ContextId };
            request.Addresses.AddRange(addresses);

            var response = await Stream.Send(request.Wrap(MessageType.TpStateGetRequest), CancellationToken.None);
            return response.Unwrap<TpStateGetResponse>()
                           .Entries.ToDictionary(x => x.Address, x => x.Data);
        }

        public async Task<string[]> SetStateAsync(Dictionary<string, ByteString> addressValuePairs)
        {
            var request = new TpStateSetRequest { ContextId = ContextId };
            request.Entries.AddRange(addressValuePairs.Select(x => new TpStateEntry { Address = x.Key, Data = x.Value }));

            var response = await Stream.Send(request.Wrap(MessageType.TpStateSetRequest), CancellationToken.None);
            return response.Unwrap<TpStateSetResponse>()
                             .Addresses.ToArray();
        }

        public async Task<string[]> DeleteStateAsync(string[] addresses)
        {
            var request = new TpStateDeleteRequest { ContextId = ContextId };
            request.Addresses.AddRange(addresses);

            var response = await Stream.Send(request.Wrap(MessageType.TpStateDeleteRequest), CancellationToken.None);
            return response.Unwrap<TpStateDeleteResponse>()
                             .Addresses.ToArray();
        }

        public async Task<bool> AddReceiptDataAsync(ByteString data)
        {
            var request = new TpReceiptAddDataRequest() { ContextId = ContextId };
            request.Data = data;

            var response = await Stream.Send(request.Wrap(MessageType.TpReceiptAddDataRequest), CancellationToken.None);
            return response.Unwrap<TpReceiptAddDataResponse>()
                             .Status == TpReceiptAddDataResponse.Types.Status.Ok;
        }

        public async Task<bool> AddEventAsync(string name, Dictionary<string, string> attributes, ByteString data)
        {
            var addEvent = new Event { EventType = name, Data = data };
            addEvent.Attributes.AddRange(attributes.Select(x => new Event.Types.Attribute { Key = x.Key, Value = x.Value }));

            var request = new TpEventAddRequest { ContextId = ContextId, Event = addEvent };

            var response = await Stream.Send(request.Wrap(MessageType.TpEventAddRequest), CancellationToken.None);
            return response.Unwrap<TpEventAddResponse>()
                             .Status == TpEventAddResponse.Types.Status.Ok;
        }
    }
}
