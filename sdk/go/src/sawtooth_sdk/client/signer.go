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

package client

import (
	"crypto/sha256"
	"crypto/sha512"
	ellcurv "github.com/btcsuite/btcd/btcec"
	"github.com/btcsuite/btcutil/base58"
	"math/big"
)

// -- Key Gen --

// GenPrivKey generates a new private key and returns it as bytes
func GenPrivKey() []byte {
	priv, err := ellcurv.NewPrivateKey(ellcurv.S256())
	if err != nil {
		panic("Failed to generate private key")
	}
	return priv.Serialize()
}

// GenPubKey generates a new public key from a given private key and returns it
// using the 33 byte compressed format
func GenPubKey(privkey []byte) []byte {
	_, pub := ellcurv.PrivKeyFromBytes(ellcurv.S256(), privkey)
	return pub.SerializeCompressed()
}

// -- Signing --

// Sign uses the given private key to calculate a signature for the given data.
// A sha256 hash of the data is first calculated and this is what is actually
// signed. Returns the signature as bytes using the compact serialization
// (which is just (r, s)).
func Sign(data, privkey []byte) []byte {
	priv, _ := ellcurv.PrivKeyFromBytes(ellcurv.S256(), privkey)

	hash := SHA256(data)

	sig, err := priv.Sign(hash)
	if err != nil {
		panic("Signing failed")
	}

	return serializeCompact(sig)
}

// Verify uses the given public key to verify that the given signature was
// created from the given data using the associated private key. A sha256 hash
// of the data is calculated first and this is what is actually used to verify
// the signature.
func Verify(data, signature, pubkey []byte) bool {
	sig := deserializeCompact(signature)
	hash := SHA256(data)
	pub, err := ellcurv.ParsePubKey(pubkey, ellcurv.S256())
	if err != nil {
		panic(err.Error())
	}
	return sig.Verify(hash, pub)
}

// -- SHA --

// SHA512 calculates a sha512 has from the given input byte slice
func SHA512(input []byte) []byte {
	hash := sha512.New()
	hash.Write(input)
	return hash.Sum(nil)
}

// SHA256 calculates a sha256 has from the given input byte slice
func SHA256(input []byte) []byte {
	hash := sha256.New()
	hash.Write(input)
	return hash.Sum(nil)
}

// -- WIF --

// PrivToWif converts a private key generated to a WIF string
func PrivToWif(priv []byte) string {
	extended := append([]byte{0x80}, priv...)
	checksum := SHA256(SHA256(extended))[:4]
	extcheck := append(extended, checksum...)
	return base58.Encode(extcheck)
}

// WifToPriv converts a WIF string to a private key
func WifToPriv(wif string) []byte {
	extcheck := base58.Decode(wif)
	return extcheck[1 : len(extcheck)-4]
}

// ---

func serializeCompact(sig *ellcurv.Signature) []byte {
	b := make([]byte, 0, 64)
	// TODO: Padding
	rbytes := pad(sig.R.Bytes(), 32)
	sbytes := pad(sig.S.Bytes(), 32)
	b = append(b, rbytes...)
	b = append(b, sbytes...)
	if len(b) != 64 {
		panic("Invalid signature length")
	}
	return b
}

func deserializeCompact(b []byte) *ellcurv.Signature {
	return &ellcurv.Signature{
		R: new(big.Int).SetBytes(b[:32]),
		S: new(big.Int).SetBytes(b[32:]),
	}
}

func pad(buf []byte, size int) []byte {
	newbuf := make([]byte, 0, size)
	padLength := size - len(buf)
	for i := 0; i < padLength; i++ {
		newbuf = append(newbuf, 0)
	}
	return append(newbuf, buf...)
}
