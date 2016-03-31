%module ECDSARecoverModule

%include <std_string.i>

%{
#include "ECDSARecover.h"
%}

using namespace std;

%exception recoverPubKeyFromSig {
   try {
      $action
   } catch (std::invalid_argument &e) {
      PyErr_SetString(PyExc_ValueError, const_cast<char*>(e.what()));
      return NULL;
   } catch (std::domain_error &e) {
      PyErr_SetString(PyExc_ValueError, const_cast<char*>(e.what()));
      return NULL;
   } catch (std::exception &e) {
      PyErr_SetString(PyExc_RuntimeError, const_cast<char*>(e.what()));
      return NULL;
   }
}
string recoverPubKeyFromSig(string msghash, string sig_r, string sig_s, int yBit);