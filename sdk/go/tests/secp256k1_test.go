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

package tests

import (
	. "sawtooth_sdk/signing"
	"testing"
)

var (
	data   = []byte{0x01, 0x02, 0x03}
	PEMSTR = `-----BEGIN EC PRIVATE KEY-----
MHQCAQEEIISGREvlByLRnbhovpK8wSd5hnymtY8hdQCOvZQ473CpoAcGBSuBBAAK
oUQDQgAEWC6TyM1jpYu3f/GGIuktDk4nM1qyOf9PEPHkRkN8zK2HxxNwDi+yN3hR
8Ag+VeTwbRRZOlBdFBsgPxz3/864hw==
-----END EC PRIVATE KEY-----
`
	PEMSTRPRIV = "8486444be50722d19db868be92bcc12779867ca6b58f2175008ebd9438ef70a9"
	ENCPEM     = `-----BEGIN EC PRIVATE KEY-----
Proc-Type: 4,ENCRYPTED
DEK-Info: AES-128-CBC,23CDF282F2217A9334A2413D78DAE04C

PQy89wdLsayP/FG68wgmL1EdlI3S5pN8ibCFrnp5OAtVNrYUD/TH9DMYVmRCNUB4
e+vXoQzd1IysjoFpV21zajSAxCmcbU4CGCDEea3GPwirOSE0ZjPHPp15IkRuGFYm
L/8e9mXvEQPAmBC0NMiltnk4/26iN7hB1QxSQQwy/Zc=
-----END EC PRIVATE KEY-----
`
	ENCPEMPRIV = "2cc32bc33935a5dbad8118abc63dfb627bb91a98d5e6310f5d60f5d65f6adb2f"
	PEMPUBSTR  = "03582e93c8cd63a58bb77ff18622e92d0e4e27335ab239ff4f10f1e446437cccad"
	ENCPEMPUB  = "0257510b4718fd79b21dee3173ffb48ab9a668a35a377be7b7dc432243a940c510"
	PUBSTR     = "035e1de3048a62f9f478440a22fd7655b80f0aac997be963b119ac54b3bfdea3b7"
	SIGSTR     = "0062bc154dca72472e66062c4539c8befb2680d79d59b3cc539dd182ff36072b199adc1118db5fc1884d50cdec9d31a2356af03175439ccb841c7b0e3ae83297"
)

func TestSigning(t *testing.T) {
	context := NewSecp256k1Context()
	priv_1 := context.NewRandomPrivateKey()
	pub_1 := context.GetPublicKey(priv_1)

	sig_1 := context.Sign(data, priv_1)

	if !context.Verify(sig_1, data, pub_1) {
		t.Error(
			"Context fails t to verify signature",
			priv_1, pub_1, sig_1,
		)
	}

	priv_2 := context.NewRandomPrivateKey()

	sig_2 := context.Sign(data, priv_2)

	if context.Verify(sig_2, data, pub_1) {
		t.Error(
			"Context verifies wrong signature",
			priv_2, pub_1, sig_2,
		)
	}

	// Verify that everything returns the right algorithm name
	assertSecp256k1(context.GetAlgorithmName(), t)
	assertSecp256k1(priv_1.GetAlgorithmName(), t)
	assertSecp256k1(pub_1.GetAlgorithmName(), t)
	assertSecp256k1(priv_2.GetAlgorithmName(), t)
}

func assertSecp256k1(name string, t *testing.T) {
	if name != "secp256k1" {
		t.Error("Wrong name", name)
	}
}

func TestPemLoader(t *testing.T) {
	// Load the keys
	priv, err := PemToSecp256k1PrivateKey(PEMSTR, "")
	if err != nil {
		t.Error("Failed to load unencrypted PEM key")
	}

	epriv, err := PemToSecp256k1PrivateKey(ENCPEM, "password")
	if err != nil {
		t.Error("Failed to load encrypted PEM key")
	}

	// Test that they match expected
	if priv.AsHex() != PEMSTRPRIV {
		t.Error("Failed to parse unencrypted PEM key")
	}

	if epriv.AsHex() != ENCPEMPRIV {
		t.Error("Failed to parse encrypted PEM key")
	}

	// Test that the correct public keys are generated
	context := NewSecp256k1Context()

	pub := context.GetPublicKey(priv).AsHex()
	epub := context.GetPublicKey(epriv).AsHex()

	if pub != PEMPUBSTR {
		t.Error("Failed to generate correct public key from unencrypted PEM key")
	}

	if epub != ENCPEMPUB {
		t.Error("Failed to generate correct public key from encrypted PEM key")
	}
}

func TestOtherSigning(t *testing.T) {
	context := CreateContext("secp256k1")
	priv := context.NewRandomPrivateKey()

	factory := NewCryptoFactory(context)
	signer := factory.NewSigner(priv)

	pub := signer.GetPublicKey()
	sig := signer.Sign(data)

	if !context.Verify(sig, data, pub) {
		t.Error(
			"Context fails t to verify signature",
			priv, pub, sig,
		)
	}
}
