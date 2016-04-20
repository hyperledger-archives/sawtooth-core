%module poet_enclave_simulator

%include <std_string.i>

%{
#include "poet_enclave.h"
%}

%include "poet_enclave.h"

%init %{
    InitializePoetEnclaveModule();
%}
%pythoncode %{
    # initialization entry point for the module
    # this implementation does not require any parameters but other
    # enclave implementations do.
    def initialize(**kwargs):
        pass
%}