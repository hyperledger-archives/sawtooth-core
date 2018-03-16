using System;
using Sawtooth.Sdk.Client;
using Sawtooth.Sdk;
using System.Net.Http;
using System.Threading.Tasks;
using System.Linq;
using PeterO.Cbor;
using Console = Colorful.Console;
using System.Drawing;

namespace Client
{
    class Program
    {
        static void Main(string[] args)
        {
            if (args != null && (args.Count() < 2 || args.Count() > 3))
            {
                Console.WriteLine("Name and Verb arguments must be set.", Color.Red);
                Console.WriteLine("Usage: dotnet run [keyname] [verb] [optional value]");
                Console.WriteLine(" dotnet run intkey set 42\t- sets initial value");
                Console.WriteLine(" dotnet run intkey inc\t- increases existing value");
                Console.WriteLine(" dotnet run intkey dec\t- decreases existing value");
                return;
            }

            var name = args[0];
            var verb = args[1];

            var obj = CBORObject.NewMap()
                                .Add("Name", name)
                                .Add("Verb", verb);
            if (args.Count() == 3)
            {
                obj.Add("Value", Int32.Parse(args[2]));
            }

            var prefix = "intkey".ToByteArray().ToSha512().ToHexString().Substring(0, 6);
            var signer = new Signer();

            var settings = new EncoderSettings()
            {
                BatcherPublicKey = signer.GetPublicKey().ToHexString(),
                SignerPublickey = signer.GetPublicKey().ToHexString(),
                FamilyName = "intkey",
                FamilyVersion = "1.0"
            };
            settings.Inputs.Add(prefix);
            settings.Outputs.Add(prefix);
            var encoder = new Encoder(settings, signer.GetPrivateKey());

            var payload = encoder.EncodeSingleTransaction(obj.EncodeToBytes());

            var content = new ByteArrayContent(payload);
            content.Headers.Add("Content-Type", "application/octet-stream");

            var httpClient = new HttpClient();

            var response = httpClient.PostAsync("http://localhost:8008/batches", content).Result;
            Console.WriteLine(response.Content.ReadAsStringAsync().Result);
        }
    }
}
