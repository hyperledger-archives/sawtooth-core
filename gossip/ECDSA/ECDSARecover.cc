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
// -----------------------------------------------------------------------------


/*
* @file	  ECDSARecover.cc
* @author Dan Middleton
* @date	  2016-01-28
* @status RESEARCH PROTOTYPE
*
* Recover public key from ECDSA Signature and associated message hash
* Given an ECDSA Signature: (r,s) and message hash, e
* Return public key, Q, as Q = r^-1(sr-eG)
* where G is the group Generator.
* Specifically written for secp256k1 curve with sha256. 
* Should not be used with other curves or hash functions.
*/

#include "ECDSARecover.h"
#include <string>
#include <iostream>
#include <sstream>
#include <iomanip>

using namespace CryptoPP;
using namespace std;

/* Recovers the public key encoded in an ECDSA signature
 * @param msgHash: message hash;
 * @param r,s: signature pair
 * @param yBit: y recovery value as defined in Certicom Sec 1 v2.
 * @return Returns point Q (public key) as a serialized x,y pair.
 */
string RecoverPubKey(Integer e, Integer r, Integer s, int yBit) {
    // use private key constructor to get the curve params
    ECDSA<ECP, SHA256>::PrivateKey tmp;
    tmp.Initialize(ASN1::secp256k1(), 2); 

    // Setup variables (lower case scalars, upper case Points)
    // p: Field modulus. #Fp
    // n: Curve modulus. #E(p)=n < #Fp=p
    // G: Curve generator
    // R: Point to be recovered from signature; initializd off curve for safety
    // x, y, exp: used for recovering point R
    Integer h(tmp.GetGroupParameters().GetCofactor());
    Integer a(tmp.GetGroupParameters().GetCurve().GetA());
    Integer b(tmp.GetGroupParameters().GetCurve().GetB());
    Integer p(tmp.GetGroupParameters().GetCurve().GetField().GetModulus()); 
    Integer n(tmp.GetGroupParameters().GetSubgroupOrder());                 
    ECPPoint G(tmp.GetGroupParameters().GetSubgroupGenerator());
    ECPPoint R(1,1);                    
    Integer x(0L), y(0L), exp(0L);      

    ECP curve(p, a, b);	                // specify params for secp256k1

    // Check inputs.
    if (r > n || r < 0) {               
        string error = "Invalid signature. r exceeds group size.\n";
        throw std::domain_error(error);
        return "";
    }
    if (s > n || s < 0) {
        string error = "Invalid signature. s exceeds group size.\n";
        throw std::domain_error(error);
        return "";
    }
    if (e.BitCount() > 256 || e < 0) {   //e may be >n, but not >sha256 length
        string error = "Invalid signature. Message hash value out of range.\n";
        throw std::domain_error(error);
        return "";
    }

    // Use r (the x coordinate of R=kG) to compute y
    // Iterate over the cofactor to try multiple possible x deriving from r.
    // x may be between n and p and ~shrunken when set to r = x mod n.
    // But x could never have been larger than the field modulus, p.
    for (int i = 0; i < (h + 1); i++) { 
        x = r + i*n; 
        if (x>p) {  
            string error = "Invalid signature: R.x exceeds field modulus.\n";
            throw std::domain_error(error);
            return "";                  
        }
        
        y = (x * x * x + 7) % p;        // computes y^2 hardcoded to secp256k
        exp = (p + 1) / 4;              // Exponentiation rule for sqrt...
        y = a_exp_b_mod_c(y, exp, p);   // ...when p = 3 mod 4 (see HAC 3.36)

        if ((yBit % 2) ^ (y % 2)) {     // yBit says if we expect y to be odd
            y = p - y;                  // sqrt(y^2)=+/-y: so may need -y
        }

        R.x = x; R.y = y;
        if (curve.VerifyPoint(R)) {     // Check if this point is on the curve
            break;                      // If so jump out of the cofactor loop
        }                               // If not then interate thru loop again

    }

    if(!curve.VerifyPoint(R)){          // Validate computed point is on curve
        string error = "Recover Pub Key: Computed point is not on curve.\n";
        throw std::domain_error(error);
        return "";
    }

    //Compute pulic key, Q, as Q=r^(-1)(sR-eG) mod p
    ECPPoint sR(curve.Multiply(s, R));       // compute s*R
    ECPPoint eG(curve.Multiply(e, G));       // compute e*G
    ECPPoint sR_eG(curve.Subtract(sR, eG));  // compute sR-eG
    Integer rInv = r.InverseMod(n);          // Compute modular inverse of r
    ECPPoint Q(curve.Multiply(rInv, sR_eG)); // Apply r_inverse to sR-eG

     
    // Check that Q actually verifies the message. 
    // (For optimization this can probably be removed.)
    // The Crypto++ verify method takes the message not a digest as input. 
    // We only have access to the digest.
    // So do signature verification from scratch.

    //If Q or QP is the identity or if it isn't on the curve then fail
    if ( (Q == curve.Identity()) 
         || (curve.Multiply(p, Q) == curve.Identity()) 
         || (!curve.VerifyPoint(Q))) {
        string error = "Recover Pub Key:" 
                       " Calculated key fails basic criteria.\n";
        throw std::domain_error(error);
        return "";
    }

    //Compute ewG + rwQ; x component of sum should equal r for sig to verify
    Integer w(s.InverseMod(n));             // Calculate s^-1
    Integer u1(a_times_b_mod_c(e, w, n));   // u1 = ew mod n
    Integer u2(a_times_b_mod_c(r, w, n));   // u2 = rw mod n
    ECPPoint u1G(curve.Multiply(u1, G));    // u1*G
    ECPPoint u2Q(curve.Multiply(u2, Q));    // u2*Q
    ECPPoint X1(curve.Add(u1G, u2Q));       // u1G + u2Q; 
    if (!curve.VerifyPoint(X1)) { 
        string error = "x1 did not verify as a point on the curve.\n"; 
        throw std::domain_error(error);
        return "";
    }

    Integer x1 = X1.x % n;                  // take x coordinate mod n
    if (r != x1) {                          // if r == x1 signature verifies
        string error = "Failed to recover pubkey."
                       " Recovered key fails to verify signature.\n";
        throw std::domain_error(error); 
        return "";
    }

#ifdef DEBUG_PUBKRECOVER
    cout << "Success recovering a pubkey from signature.\n";
    cout << "Computed R..." << endl;
    cout << "  R.x: " << R.x << endl;      
    cout << "  R.y: " << R.y << endl;
    cout << "Computed Q..." << endl;
    cout << "  Q.x: " << Q.x << endl;
    cout << "  Q.y: " << Q.y << endl;
    cout << "Q hex... " << endl;
    cout << "  Q.x: " << std::hex << Q.x << endl;
    cout << "  Q.y: " << Q.y << endl << std::dec;
    cout << "Input r:     " << r << endl;
    cout << "Computed x1: " << x1 << endl;
#endif

    // Format output 
    std::stringstream xss, yss, stream;
    xss << std::hex << Q.x;                   //Get hex strings of points
    yss << std::hex << Q.y;

    // Strip off cryptopp's hex "h" tag.
    string xstr = xss.str(); xstr.resize(xstr.size()-1);  // xstr.pop_back(); 
    string ystr = yss.str(); ystr.resize(ystr.size()-1);  // ystr.pop_back();
    stream << std::setw(64) << std::setfill('0') << xstr; // Pad out 64 nibbles
    stream << std::setw(64) << std::setfill('0') << ystr; // Pad out 64 nibbles
    return stream.str();
}

// TEST method 
// Expects signature computed from the following
// d:2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7aeh
// k:48692452077975311141641379449682050563269990734773417387024709146437866544976 (note: dec)
// e:fcde2b2edba56bf408601fb721fe9b5c338d10ee429ea04fae5511b68fbf8fb9h
// Should have created an r,s:
// r:73822833206246044331228008262087004113076292229679808334250850393445001014761
// s:58995174607243353628346858794753620798088291196940745194581481841927132845752
void Test(Integer e, Integer r, Integer s){
    ECDSA<ECP, SHA256>::PrivateKey tmp;
    tmp.Initialize(ASN1::secp256k1(), 2); //use private key constructor to get the curve params

    //Setup variables
    Integer h(tmp.GetGroupParameters().GetCofactor());
    Integer a(tmp.GetGroupParameters().GetCurve().GetA());
    Integer b(tmp.GetGroupParameters().GetCurve().GetB());
    Integer p(tmp.GetGroupParameters().GetCurve().GetField().GetModulus());
    Integer n(tmp.GetGroupParameters().GetSubgroupOrder());
    ECPPoint G(tmp.GetGroupParameters().GetSubgroupGenerator());
    ECP curve(p, a, b);
    Integer d("2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7aeh");

    //derive k
    Integer k("48692452077975311141641379449682050563269990734773417387024709146437866544976"); //yanked from python
    Integer w = s.InverseMod(n);
    cout << "TEST: Expected k: " << k << endl;
    ECPPoint RPrime(curve.Multiply(k,G));
    Integer rx = RPrime.x %n;
    Integer ry = RPrime.y %n;
    cout << "TEST: R computed from k\n";
    cout << "TEST: kG.x mod n: " << rx << endl; 
    cout << "TEST: kG.y mod n: " << ry << endl;
    k = 0;
    cout << "TEST: Cleared k: " << k << endl;
    k = (e + r*d) %n;
    k = w * k %n;
    ECPPoint R(curve.Multiply(k, G));
    if(r == R.x) {
        cout << "TEST: k verified by r==R.x\n" << "TEST: k: " << k << endl;
    } else {
        cerr << "TEST: k computation FAILED\n" << "TEST: k: " << k << endl;
    }
    cout << "TEST: computed R.x: " << R.x << endl;

    //Derive e = sk - rd 
    Integer u = s * k % n;
    Integer v = r * d % n;
    v = n - v; 
    Integer derived_e = u + v %n;
    if(e == derived_e) {
        cout << "TEST: e verified by sk-rd\n" << "TEST: e': " << derived_e << endl;
    } else {
        cerr << "TEST: e compuation FAILED\n" << "TEST: e': " << derived_e << endl;
    }
}

string recover_pubkey(string msgHash, string sig_r, string sig_s, int yBit) {
    if (msgHash.empty() || sig_r.empty() || sig_s.empty() || yBit > 3 || yBit < 0)
        throw std::invalid_argument("Empty string or invalid yBit value.\n");
    try {
        Integer e(msgHash.data());
        Integer r(sig_r.data());
        Integer s(sig_s.data());
#ifdef DEBUG_PUBKRECOVER
        cout << "In c++ code" << endl;
        cout << "e:      " << e << endl;
        cout << "hex(e): " << std::hex << e << endl;
        cout << "r:      " << std::dec << r << endl;
        cout << "s:      " << s << endl;
        cout << "ybit:   " << yBit << endl;
#endif
#ifdef TEST_PUBKRECOVER
        test(e, r, s);
#endif
        return RecoverPubKey(e, r, s, yBit);
    }
    catch (std::domain_error e) {
        throw(e);
        return "";
    }
    catch (exception e) {
        throw(e);
        return "";
    }
}
