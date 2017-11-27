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

// -- Keys --

// A private key instance. The underlying content is dependent on
// implementation.
type PrivateKey interface {
	// Returns the algorithm name used for this private key.
	GetAlgorithmName() string

	// Returns the private key encoded as a hex string.
	AsHex() string

	// Returns the private key bytes.
	AsBytes() []byte
}

// A public key instance. The underlying content is dependent on
// implementation.
type PublicKey interface {
	// Returns the algorithm name used for this public key.
	GetAlgorithmName() string

	// Returns the public key encoded as a hex string.
	AsHex() string

	// Returns the public key bytes.
	AsBytes() []byte
}

// -- Context --

// A context for a cryptographic signing algorithm.
type Context interface {
	// Returns the algorithm name used for this context.
	GetAlgorithmName() string

	// Generates a new random private key.
	NewRandomPrivateKey() PrivateKey

	// Produces a public key for the given private key.
	GetPublicKey(private_key PrivateKey) PublicKey

	// Sign uses the given private key to calculate a signature for
	// the given data.
	Sign(message []byte, private_key PrivateKey) []byte

	// Verify uses the given public key to verify that the given
	// signature was created from the given data using the associated
	// private key.
	Verify(signature []byte, message []byte, public_key PublicKey) bool
}

// Returns a Context instance by name.
func CreateContext(algorithmName string) Context {
	if algorithmName == "secp256k1" {
		return NewSecp256k1Context()
	}

	panic("No such algorithm")
}

// -- Signer --

// A convenient wrapper of Context and PrivateKey.
type Signer struct {
	context     Context
	private_key PrivateKey
}

// Signs the given message.
func (self *Signer) Sign(message []byte) []byte {
	return self.context.Sign(message, self.private_key)
}

// Returns the public key for this Signer instance.
func (self *Signer) GetPublicKey() PublicKey {
	return self.context.GetPublicKey(self.private_key)
}

// -- CryptoFactory --

// A factory for generating Signers.
type CryptoFactory struct {
	context Context
}

// Creates a factory for generating Signers.
func NewCryptoFactory(context Context) *CryptoFactory {
	return &CryptoFactory{context: context}
}

// Returns the context that backs this Factory instance.
func (self *CryptoFactory) GetContext() Context {
	return self.context
}

// Creates a new Signer for the given private key.
func (self *CryptoFactory) NewSigner(private_key PrivateKey) *Signer {
	return &Signer{self.context, private_key}
}
