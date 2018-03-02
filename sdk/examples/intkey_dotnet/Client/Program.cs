﻿using System;
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
            if (args == null && (args.Count() < 2 || args.Count() > 3))
            {
                Console.WriteLine("Name and Verb arguments must be set.");
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

            var payload = encoder.EncodeSingleTransaction(obj.EncodeToBytes());

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
