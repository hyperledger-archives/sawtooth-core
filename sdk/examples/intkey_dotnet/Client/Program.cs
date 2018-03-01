using System;
using Sawtooth.Sdk.Client;
using Sawtooth.Sdk;
using System.Net.Http;
using System.Threading.Tasks;
using System.Linq;
using PeterO.Cbor;

namespace Client
{
    class Program
    {
        static void Main(string[] args)
        {
            Console.WriteLine("Hello World!");

            var obj = CBORObject.NewMap()
                                .Add("name", "tomislav")
                                .Add("value", 1);
            
            var b = obj.EncodeToBytes();

            var a = CBORObject.DecodeFromBytes(b);
            return;

            var prefix = "myintkey".ToByteArray().ToSha512().ToHexString().Substring(0, 6);
            var signer = new Signer();

            var settings = new EncoderSettings()
            {
                BatcherPublicKey = signer.GetPublicKey().ToHexString(),
                SignerPublickey = signer.GetPublicKey().ToHexString(),
                FamilyName = "myintkey",
                FamilyVersion = "1.0"
            };
            settings.Inputs.Add(prefix);
            settings.Outputs.Add(prefix);
            var encoder = new Encoder(settings, signer.GetPrivateKey());

            var payload = encoder.EncodeSingleTransaction(new[] { (byte)6 });

            var content = new ByteArrayContent(payload);
            content.Headers.Add("Content-Type", "application/octet-stream");

            var httpClient = new HttpClient();

            var task = httpClient.PostAsync("http://localhost:8008/batches", content);
            task.Wait(TimeSpan.FromSeconds(5));

            if (task.Status == TaskStatus.RanToCompletion)
            {
                Console.WriteLine(task.Result.Content.ReadAsStringAsync().Result);
            }
            else
            {
                Console.WriteLine("Timeout occured. Server didn't respond.");
            }
        }
    }
}
