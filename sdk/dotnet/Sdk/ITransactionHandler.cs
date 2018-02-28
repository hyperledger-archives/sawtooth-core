using System;
using System.Threading.Tasks;
using Sawtooth.Sdk.Processor;

namespace Sawtooth.Sdk
{
    public interface ITransactionHandler
    {
        string FamilyName
        {
            get;
        }

        string Version
        {
            get;
        }

        string[] Namespaces
        {
            get;
        }

        Task Apply(TpProcessRequest request, Context context);
    }
}
