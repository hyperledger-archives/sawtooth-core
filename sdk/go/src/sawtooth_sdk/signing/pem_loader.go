/**
 * Copyright 2017 Intel Corporation
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * ------------------------------------------------------------------------------
 */

package signing

// #cgo LDFLAGS: -lcrypto
// #include "../../../../c/c11_support.h"
// #include "../../../../c/c11_support.c"
// #include "../../../../c/loader.c"
import "C"

import "fmt"

func loadPemKey(pemstr string, pemstrLen int, password string) (priv_key string, pub_key string, err error) {
	cPemstr := C.CString(pemstr)
	cPemstrLen := C.size_t(pemstrLen)
	cPassword := C.CString(password)
	cOutPrivKey := C.CString("-----------------------------------------------------------------")
	cOutPubKey := C.CString("-----------------------------------------------------------------------------------------------------------------------------------")
	errnum := C.load_pem_key(cPemstr, cPemstrLen, cPassword, cOutPrivKey, cOutPubKey)
	if errnum < 0 {
		var errstr string
		switch errnum {
		case -1:
			errstr = "Failed to decrypt or decode private key"
		case -2:
			errstr = "Failed to create new big number context"
		case -3:
			errstr = "Failed to load group"
		case -4:
			errstr = "Failed to load private key"
		case -5:
			errstr = "Failed to load public key point"
		case -6:
			errstr = "Failed to construct public key from point"
		}
		return "", "", fmt.Errorf(errstr)
	}
	return C.GoString(cOutPrivKey), C.GoString(cOutPubKey), nil
}
