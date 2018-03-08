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
            var validatorAddress = args.Any() ? args.First() : "tcp://127.0.0.1:4004";

            var processor = new TransactionProcessor(validatorAddress);
            processor.AddHandler(new IntKeyProcessor());
            processor.Start();

            Console.CancelKeyPress += delegate { processor.Stop(); };
        }
    }
}
