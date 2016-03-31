%module poet_enclave_simulator

%include <std_string.i>

%{
#include "poet_enclave.h"
%}

%include "poet_enclave.h"

%init %{
    InitializePoetEnclaveModule();
%}
