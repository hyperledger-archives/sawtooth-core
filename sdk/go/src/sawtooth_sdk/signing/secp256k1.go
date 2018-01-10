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

import (
	"crypto/sha256"
	"crypto/sha512"
	"encoding/hex"
	ellcurv "github.com/btcsuite/btcd/btcec"
	"math/big"
)

var cachedCurve = ellcurv.S256()

// -- Private Key --

type Secp256k1PrivateKey struct {
	private_key []byte
}

// Creates a PrivateKey instance from private key bytes.
func NewSecp256k1PrivateKey(private_key []byte) PrivateKey {
	return &Secp256k1PrivateKey{private_key}
}

// PemToSecp256k1PrivateKey converts a PEM string to a private key.
func PemToSecp256k1PrivateKey(pem string, password string) (*Secp256k1PrivateKey, error) {
	priv, err := pemToPriv(pem, password)
	if err != nil {
		return nil, err
	}

	return &Secp256k1PrivateKey{priv}, nil
}

// Returns the string "secp256k1".
func (self *Secp256k1PrivateKey) GetAlgorithmName() string {
	return "secp256k1"
}

// Returns the private key as a hex-encoded string.
func (self *Secp256k1PrivateKey) AsHex() string {
	return hex.EncodeToString(self.private_key)
}

// Returns the bytes of the private key.
func (self *Secp256k1PrivateKey) AsBytes() []byte {
	return self.private_key
}

// -- Public Key --

type Secp256k1PublicKey struct {
	public_key []byte
}

// Creates a PublicKey instance from public key bytes.
func NewSecp256k1PublicKey(public_key []byte) PublicKey {
	return &Secp256k1PublicKey{public_key}
}

// Returns the string "secp256k1".
func (self *Secp256k1PublicKey) GetAlgorithmName() string {
	return "secp256k1"
}

// Returns the public key as a hex-encoded string.
func (self *Secp256k1PublicKey) AsHex() string {
	return hex.EncodeToString(self.public_key)
}

// Returns the bytes of the public key.
func (self *Secp256k1PublicKey) AsBytes() []byte {
	return self.public_key
}

// -- Context --

type Secp256k1Context struct {
	curve *ellcurv.KoblitzCurve
}

// Returns a new secp256k1 context.
func NewSecp256k1Context() Context {
	return &Secp256k1Context{ellcurv.S256()}
}

// Returns the string "secp256k1".
func (self *Secp256k1Context) GetAlgorithmName() string {
	return "secp256k1"
}

// Generates a new random secp256k1 private key.
func (self *Secp256k1Context) NewRandomPrivateKey() PrivateKey {
	priv, _ := ellcurv.NewPrivateKey(cachedCurve)

	return &Secp256k1PrivateKey{priv.Serialize()}
}

// Produces a public key for the given private key.
func (self *Secp256k1Context) GetPublicKey(private_key PrivateKey) PublicKey {
	_, public_key := ellcurv.PrivKeyFromBytes(
		cachedCurve,
		private_key.AsBytes())

	return NewSecp256k1PublicKey(public_key.SerializeCompressed())
}

// Sign uses the given private key to calculate a signature for the
// given data. A sha256 hash of the data is first calculated and this
// is what is actually signed. Returns the signature as bytes using
// the compact serialization (which is just (r, s)).
func (self *Secp256k1Context) Sign(message []byte, private_key PrivateKey) []byte {
	priv, _ := ellcurv.PrivKeyFromBytes(
		self.curve,
		private_key.AsBytes())

	hash := doSHA256(message)

	sig, err := priv.Sign(hash)
	if err != nil {
		panic("Signing failed")
	}

	return serializeCompact(sig)
}

// Verify uses the given public key to verify that the given signature
// was created from the given data using the associated private key. A
// sha256 hash of the data is calculated first and this is what is
// actually used to verify the signature.
func (self *Secp256k1Context) Verify(signature []byte, message []byte, public_key PublicKey) bool {
	sig := deserializeCompact(signature)
	hash := doSHA256(message)

	pub, err := ellcurv.ParsePubKey(
		public_key.AsBytes(),
		self.curve)
	if err != nil {
		panic(err.Error())
	}

	return sig.Verify(hash, pub)
}

// -- SHA --

func doSHA512(input []byte) []byte {
	hash := sha512.New()
	hash.Write(input)
	return hash.Sum(nil)
}

func doSHA256(input []byte) []byte {
	hash := sha256.New()
	hash.Write(input)
	return hash.Sum(nil)
}

func pemToPriv(pem string, password string) ([]byte, error) {
	pemlen := len(pem)
	priv, _, err := loadPemKey(pem, pemlen, password)
	if err != nil {
		return nil, err
	}
	return hex.DecodeString(priv)
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
