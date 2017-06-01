package main

import (
	"burrow/evm/sha3"
	. "burrow/word256"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
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

type RespBody struct {
	Data string
	Link string
	Head string
}

func (r *RespBody) String() string {
	return fmt.Sprintf(`
Data: %v
Link: %v
Head: %v
`, r.Data, r.Link, r.Head)
}

func ParseRespBody(resp *http.Response) (*RespBody, error) {
	defer resp.Body.Close()
	buf, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	if len(buf) == 0 {
		return nil, fmt.Errorf("Nothing at that address")
	}

	body := new(RespBody)
	err = json.Unmarshal(buf, body)

	return body, err
}
