using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Threading.Tasks;
using Google.Protobuf;
using Sawtooth.Sdk.Client;
using Sawtooth.Sdk.Processor;
using Console = Colorful.Console;

namespace Program
{
    class Program
    {
        static void Main(string[] args)
        {
            var validatorAddress = "tcp://localhost:4004";
            var apiAddress = "http://localhost:8008";

            // Task.Run(async () =>
            // {
            //     var processor = new TransactionProcessor(validatorAddress);
            //     processor.AddHandler(new IntKeyProcessor());
            //     await processor.Start();
            // });
            
            // Task.Run(async () =>
            // {
            //     for (int i = 0; i <= 5; i++)
            //     {
            //         await Task.Delay(TimeSpan.FromSeconds(20));

            //         var signer = new Signer(); // generates new private key
            //         var prefix = "myintkey".ToByteArray().ToSha512().ToHexString().Substring(0, 6);

            //         var payload = "Tomislav Markovski from New York".ToByteArray();

            //         var settings = new EncoderSettings();
            //         settings.FamilyName = "myintkey";
            //         settings.FamilyVersion = "1.0";
            //         settings.Inputs.Add(prefix);
            //         settings.Outputs.Add(prefix);
            //         settings.SignerPublickey = settings.BatcherPublicKey = signer.GetPublicKey().ToHexString();

            //         var encoder = new Encoder(settings, signer.GetPrivateKey());
            //         var encodedData = encoder.EncodeSingleTransaction(payload);

            //         var content = new ByteArrayContent(encodedData);
            //         content.Headers.Add("Content-Type", "application/octet-stream");

            //         var httpClient = new HttpClient();
            //         var response = await httpClient.PostAsync($"{apiAddress}/batches", content);

            //         Debug.WriteLine(await response.Content.ReadAsStringAsync());
            //     }
            // });

            Console.WriteLine("This is a colorful text", Color.Green);

            Console.ReadLine();
        }
    }
}
