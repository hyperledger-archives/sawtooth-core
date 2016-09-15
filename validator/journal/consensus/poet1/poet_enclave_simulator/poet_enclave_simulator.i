%module poet_enclave_simulator

%include <std_string.i>
%include <exception.i>

%exception  {
	try {
		$function
	} catch(MemoryError e) {
		SWIG_exception(SWIG_MemoryError, e.what());
	} catch(IOError e) {
		SWIG_exception(SWIG_IOError, e.what());
	} catch(RuntimeError e) {
		SWIG_exception(SWIG_ValueError, e.what());
	} catch(IndexError e) {
		SWIG_exception(SWIG_ValueError, e.what());
	} catch(TypeError e) {
		SWIG_exception(SWIG_ValueError, e.what());
	} catch(DivisionByZero e) {
		SWIG_exception(SWIG_DivisionByZero, e.what());
	} catch(OverflowError e) {
		SWIG_exception(SWIG_OverflowError, e.what());
	} catch(SyntaxError e) {
		SWIG_exception(SWIG_SyntaxError, e.what());
	} catch(ValueError e) {
		SWIG_exception(SWIG_ValueError, e.what());
	} catch(SystemError e) {
		SWIG_exception(SWIG_SystemError, e.what());
	} catch(UnknownError e) {
		SWIG_exception(SWIG_UnknownError, e.what());
	} catch(...) {
		SWIG_exception(SWIG_RuntimeError,"Unknown exception");
	}
}


%{
#include "common.h"
%}
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