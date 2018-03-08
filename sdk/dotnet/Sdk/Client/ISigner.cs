using System;
using System.Threading.Tasks;

namespace Sawtooth.Sdk.Client
{
    /// <summary>
    /// Represents a signer contract. This can be used to sign transactions outside of the <see cref="T:Sawtooth.Sdk.Client.Signer"/> class.
    /// </summary>
    public interface ISigner
    {
        byte[] Sign(byte[] digest);

        byte[] GetPublicKey();
    }
}
