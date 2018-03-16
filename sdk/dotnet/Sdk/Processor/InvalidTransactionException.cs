using System;
namespace Sawtooth.Sdk.Processor
{
    public class InvalidTransactionException : Exception
    {
        public InvalidTransactionException(string message) : base(message)
        {
        }

        public InvalidTransactionException() : base("Transaction was invalid")
        {
        }
    }
}
