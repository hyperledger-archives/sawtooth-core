// Copyright 2016 Intel Corporation
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
// ------------------------------------------------------------------------------


/*
*
* @file	  ECDSARecover.h
* @author Dan Middleton
* @date	  2016-01-28
* @status RESEARCH PROTOTYPE
*
* Recover public key from ECDSA Signature
* Given an ECDSA Signature: (r,s) and message hash, e
* Return public key, Q, as Q = r^-1(sr-eG)
* where G is the group Generator.
* Specifically written for secp256k1 curve. Should not be used with other curves.
*/

#include <string>
#include <cryptopp/eccrypto.h>
#include <cryptopp/asn.h>
#include <cryptopp/ecp.h>
#include <cryptopp/oids.h>
#include <cryptopp/base32.h>
#include <cryptopp/integer.h>


/* Recovers the public key encoded in an ECDSA signature
 * @param msgHash: message hash;
 * @param r,s: signature pair
 * @param yBit: y recovery value as defined in Certicom Sec 1 v2.
 * @return Returns point Q (public key) as a serialized x,y pair.
*/
std::string recover_pubkey(std::string msgHash, std::string sig_r, std::string sig_s, int yBit);

//Internally it calls a big integer version.  This header is intended for swig
//so we don't expose that method here.
//string RecoverPubKey(Integer msgHash, Integer sig_r, Integer sig_s, int yBit);
