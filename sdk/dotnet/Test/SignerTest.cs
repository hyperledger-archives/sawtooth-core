using System;
using System.Linq;
using Sawtooth.Sdk.Client;
using Xunit;

namespace Sawtooth.Sdk.Test
{
    public class SignerTest
    {
        [Fact]
        public void SignAndVerifyData()
        {
            var signer = new Signer();
            var message = "Sample message".ToByteArray();

            var signature = signer.Sign(message);

            var verify = Signer.Verify(message, signature, signer.GetPublicKey());
            Assert.True(verify);
        }
    }
}
