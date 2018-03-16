using System.Collections.Generic;

namespace Sawtooth.Sdk.Client
{
    public class EncoderSettings
    {
        public EncoderSettings()
        {
            Inputs = new List<string>();
            Outputs = new List<string>();
        }

        public string FamilyName { get; set; }
        public string FamilyVersion { get; set; }
        public List<string> Inputs { get; set; }
        public List<string> Outputs { get; set; }
        public string SignerPublickey { get; set; }
        public string BatcherPublicKey { get; set; }
    }
}