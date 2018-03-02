using System;
using System.Linq;
using System.Security.Cryptography;
using System.Text;

namespace Sawtooth.Sdk.Client
{
    public static class ClientExtensions
    {
        public static string ToHexString(this byte[] data) => String.Concat(data.Select(x => x.ToString("x2")));

        public static byte[] ToSha256(this byte[] data) => SHA256.Create().ComputeHash(data);

        public static byte[] ToSha512(this byte[] data) => SHA512.Create().ComputeHash(data);

        public static byte[] ToByteArray(this string data) => Encoding.UTF8.GetBytes(data);
    }
}
