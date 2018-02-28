using System;
using System.Threading.Tasks;
using Sawtooth.Sdk;
using Sawtooth.Sdk.Processor;
using Sawtooth.Sdk.Client;
using System.Diagnostics;
using System.Text;
using System.Linq;
using Google.Protobuf;

namespace Program
{
    public class IntKeyProcessor : ITransactionHandler
    {
        public string FamilyName { get => "myintkey"; }
        public string Version { get => "1.0"; }
        public string[] Namespaces { get => new[] { FamilyName.ToByteArray().ToSha512().ToHexString().Substring(0, 6) }; }

        public async Task Apply(TpProcessRequest request, Context context)
        {
            var state = await context.GetState(new[] { "01" });

            if (state != null && state.Any())
            {
                Debug.WriteLine("State found");
                await context.SetState(new TpStateEntry[] { new TpStateEntry() { Address = "01", Data = ByteString.CopyFrom(new byte[] { (byte)(state.First().Data.First() + 1) }) } });
            }
            else
            {
                Debug.WriteLine("No state");
                await context.SetState(new TpStateEntry[] { new TpStateEntry() { Address = "01", Data = ByteString.CopyFrom(new byte[] { 1 }) } });
            }


            Debug.WriteLine($"Request received by tx processor: {Encoding.UTF8.GetString(request.Payload.ToByteArray())} Context {request.ContextId}");

            //return Task.CompletedTask;
        }
    }
}
