using System;
using System.Threading.Tasks;
using Sawtooth.Sdk;
using Sawtooth.Sdk.Processor;
using Sawtooth.Sdk.Client;
using System.Diagnostics;
using System.Text;
using System.Linq;
using Google.Protobuf;
using System.Collections.Generic;

namespace Program
{
    public class IntKeyProcessor : ITransactionHandler
    {
        const string familyName = "myintkey";

        public string FamilyName { get => familyName; }
        public string Version { get => "1.0"; }

        readonly string PREFIX = familyName.ToByteArray().ToSha512().ToHexString().Substring(0, 6);

        public string[] Namespaces { get => new[] { PREFIX }; }

        public async Task Apply(TpProcessRequest request, Context context)
        {
            var a = "name".ToByteArray().ToSha512().ToHexString();
            var address = PREFIX + a.Substring(a.Length - 64, 64);
            var state = await context.GetState(new[] { address });

            if (state != null && state.Any())
            {
                Console.WriteLine("State found");
                int value = state.First().Value.FirstOrDefault() + 1;

                Console.WriteLine($"Setting new value: {value}");
                await context.SetState(new Dictionary<string, ByteString>()
                    {
                        { address, ByteString.CopyFrom(new [] { (byte)value }) }
                    });
            }
            else
            {
                Console.WriteLine("No state found");
                int value = 0;
                await context.SetState(new Dictionary<string, ByteString>()
                    {
                        { address, ByteString.CopyFrom(new [] { (byte)value }) }
                    });
            }

            Console.WriteLine($"Request received by tx processor: {Encoding.UTF8.GetString(request.Payload.ToByteArray())} Context {request.ContextId}");
        }
    }
}
