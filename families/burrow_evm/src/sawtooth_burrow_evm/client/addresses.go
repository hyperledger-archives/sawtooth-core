package burrow_evm_client

import (
	"burrow/evm/sha3"
	. "burrow/word256"
	"fmt"
	"sawtooth_sdk/client"
)

const (
	PRIVLEN   = 32
	PUBLEN    = 33
	ADDRLEN   = 35 * 2
	VMADDRLEN = 20
)

func PrivToAddr(priv []byte) (string, error) {
	if len(priv) != PRIVLEN {
		return "", fmt.Errorf(
			"Incorrect private key length (%v), should be %v",
			len(priv), PRIVLEN,
		)
	}
	pub := client.GenPubKey(priv)
	return PubToAddr(pub)
}

func PubToAddr(pub []byte) (string, error) {
	if len(pub) != PUBLEN {
		return "", fmt.Errorf(
			"Incorrect public key length (%v), should be %v",
			len(pub), PUBLEN,
		)
	}
	sha := sha3.Sha3(pub)[:20]
	return VmAddrToAddr(sha)
}

func VmAddrToAddr(vm []byte) (string, error) {
	if len(vm) != VMADDRLEN {
		return "", fmt.Errorf(
			"Incorrect EVM address length (%v), should be %v",
			len(vm), VMADDRLEN,
		)
	}
	a := PREFIX + client.MustEncode(RightPadBytes(vm, 32))
	if len(a) != ADDRLEN {
		return "", fmt.Errorf(
			"Malformed address (%v): Incorrect length (%v != 70)", a, len(a),
		)
	}
	return a, nil
}
