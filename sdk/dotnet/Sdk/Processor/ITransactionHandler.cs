using System;
using System.Threading.Tasks;
using Sawtooth.Sdk.Processor;

namespace Sawtooth.Sdk.Processor
{
    public interface ITransactionHandler
    {
        string FamilyName { get; }

        string Version { get; }

        string[] Namespaces { get; }

        Task ApplyAsync(TpProcessRequest request, TransactionContext context);
    }
}
