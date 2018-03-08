using System;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using Org.BouncyCastle.OpenSsl;
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

            var verify = Signer.Verify(message, signer.Sign(message), signer.GetPublicKey());
            Assert.True(verify);
        }

        [Fact]
        public void SignAndFailVerify()
        {
            var signer = new Signer();
            var message = "Sample message".ToByteArray();

            var anotherSigner = new Signer();

            var verify = Signer.Verify(message, signer.Sign(message), anotherSigner.GetPublicKey());
            Assert.False(verify);
        }

        [Fact]
        public void CreateSignerFromPem()
        {
            var fileStream = File.OpenRead("Resources/mykey.pem");
            var signer = new Signer(fileStream, null);

            var pubKey = signer.GetPublicKey();
            var privKey = signer.GetPrivateKey();

            Assert.Equal(65, pubKey.Length);
        }

        [Fact]
        public void CreateSigner_FromPem_PasswordProtected()
        {
            var fileStream = System.IO.File.OpenRead("Resources/mykey_protected.pem");
            var signer = new Signer(fileStream, new PasswordFinder("supersecret"));

            var pubKey = signer.GetPublicKey();
            var privKey = signer.GetPrivateKey();

            Assert.Equal(65, pubKey.Length);
        }

        // Helper class to pass password for the signer
        class PasswordFinder : IPasswordFinder
        {
            readonly string password;

            internal PasswordFinder(string password)
            {
                this.password = password;
            }

            public char[] GetPassword() => password.ToCharArray();
        }
    }
}
