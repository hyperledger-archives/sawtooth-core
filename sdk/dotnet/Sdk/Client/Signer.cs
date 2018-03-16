using System.IO;
using System.Linq;
using System.Threading.Tasks;
using Org.BouncyCastle.Asn1.X9;
using Org.BouncyCastle.Crypto;
using Org.BouncyCastle.Crypto.Digests;
using Org.BouncyCastle.Crypto.Generators;
using Org.BouncyCastle.Crypto.Parameters;
using Org.BouncyCastle.Crypto.Signers;
using Org.BouncyCastle.Math;
using Org.BouncyCastle.OpenSsl;
using Org.BouncyCastle.Security;

namespace Sawtooth.Sdk.Client
{
    public class Signer : ISigner
    {
        readonly static X9ECParameters Secp256k1 = ECNamedCurveTable.GetByName("secp256k1");
        readonly static ECDomainParameters DomainParams = new ECDomainParameters(Secp256k1.Curve, Secp256k1.G, Secp256k1.N, Secp256k1.H);

        readonly ECPrivateKeyParameters PrivateKey;

        /// <summary>
        /// Initializes a new instance of the <see cref="T:Sawtooth.Sdk.Client.Signer"/> class and generates new private key
        /// </summary>
        public Signer() : this(GeneratePrivateKey())
        {
        }

        /// <summary>
        /// Initializes a new instance of the <see cref="T:Sawtooth.Sdk.Client.Signer"/> class with a given private key
        /// </summary>
        /// <param name="privateKey">Private key.</param>
        public Signer(byte[] privateKey)
        {
            PrivateKey = new ECPrivateKeyParameters(new BigInteger(1, privateKey), DomainParams);
        }

        /// <summary>
        /// Initializes a new instance of the <see cref="T:Sawtooth.Sdk.Client.Signer"/> class from a PEM data stream
        /// </summary>
        /// <param name="pemStream">Pem stream.</param>
        /// <param name="passwordFinder">Password finder.</param>
        public Signer(Stream pemStream, IPasswordFinder passwordFinder = null)
        {
            var pemReader = new PemReader(new StreamReader(pemStream), passwordFinder);
            var KeyParameter = (AsymmetricCipherKeyPair)pemReader.ReadObject();

            PrivateKey = (ECPrivateKeyParameters)KeyParameter.Private;
        }

        #region ISigner methods

        /// <summary>
        /// Sign the specified message with the associated private key
        /// </summary>
        /// <returns>The sign.</returns>
        /// <param name="digest">Digest.</param>
        public byte[] Sign(byte[] digest)
        {
            var signer = new ECDsaSigner(new HMacDsaKCalculator(new Sha256Digest()));
            signer.Init(true, PrivateKey);
            var signature = signer.GenerateSignature(digest);

            var R = signature[0];
            var S = signature[1];

            // Ensure low S
            if (!(S.CompareTo(Secp256k1.N.ShiftRight(1)) <= 0))
            {
                S = Secp256k1.N.Subtract(S);
            }

            return R.ToByteArrayUnsigned().Concat(S.ToByteArrayUnsigned()).ToArray();
        }

        /// <summary>
        /// Returns the public key from the private key
        /// </summary>
        /// <returns>The public key.</returns>
        public byte[] GetPublicKey()
        {
            var Q = Secp256k1.G.Multiply(PrivateKey.D);
            return new ECPublicKeyParameters(Q, DomainParams).Q.Normalize().GetEncoded();
        }

        #endregion

        /// <summary>
        /// Returns the pirvate key associated with this instance
        /// </summary>
        /// <returns>The private key.</returns>
        public byte[] GetPrivateKey() => PrivateKey.D.ToByteArray();

        #region Static methods

        /// <summary>
        /// Verify the specified message and signature against the public key.
        /// </summary>
        /// <returns>The verify.</returns>
        /// <param name="digest">Digest.</param>
        /// <param name="signature">Signature.</param>
        /// <param name="publicKey">Public key.</param>
        public static bool Verify(byte[] digest, byte[] signature, byte[] publicKey)
        {
            var X = new BigInteger(1, publicKey.Skip(1).Take(32).ToArray());
            var Y = new BigInteger(1, publicKey.Skip(33).Take(32).ToArray());
            var point = Secp256k1.Curve.CreatePoint(X, Y);

            var R = new BigInteger(1, signature.Take(32).ToArray());
            var S = new BigInteger(1, signature.Skip(32).ToArray());

            var signer = new ECDsaSigner(new HMacDsaKCalculator(new Sha256Digest()));
            signer.Init(false, new ECPublicKeyParameters(point, DomainParams));
            return signer.VerifySignature(digest, R, S);
        }

        /// <summary>
        /// Generates random private key
        /// </summary>
        /// <returns>The private key.</returns>
        public static byte[] GeneratePrivateKey()
        {
            var keyParams = new ECKeyGenerationParameters(DomainParams, new SecureRandom());

            var generator = new ECKeyPairGenerator("ECDSA");
            generator.Init(keyParams);

            var keyPair = generator.GenerateKeyPair();
            return (keyPair.Private as ECPrivateKeyParameters).D.ToByteArray();
        }

        #endregion
    }
}
