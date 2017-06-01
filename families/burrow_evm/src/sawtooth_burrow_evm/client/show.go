package main

import (
	"encoding/base64"
	"fmt"
	"github.com/golang/protobuf/proto"
	"github.com/jessevdk/go-flags"
	"net/http"
	. "sawtooth_burrow_evm/protobuf/evm_pb2"
	"sawtooth_sdk/client"
)

type Show struct {
	Private string `short:"k" long:"key" description:"A hex encoded private key to derive an address from for accessing state."`
	Public  string `short:"p" long:"public" description:"A hex encoded public key to derive an address from for accessing state."`
	Address string `short:"a" long:"address" description:"A hex encoded VM address for accessing state."`
	Url     string `short:"U" long:"url" description:"The REST API URL to connect to when sending the transaction." default:"http://127.0.0.1:8080"`
}

func (s *Show) Name() string {
	return "show"
}

func (s *Show) Register(p *flags.Parser) error {
	_, err := p.AddCommand("show", "Show all data associated with the given address", "", s)
	return err
}

func (s *Show) Do() (err error) {
	n := 0
	if s.Private != "" {
		n += 1
	}
	if s.Public != "" {
		n += 1
	}
	if s.Address != "" {
		n += 1
	}

	if n != 1 {
		return fmt.Errorf("Must pass exactly one of {-k PRIVATE, -p PUBLIC, -a ADDRESS}")
	}

	var address string
	if s.Private != "" {
		priv := client.MustDecode(s.Private)
		address, err = PrivToAddr(priv)
		if err != nil {
			return
		}
	}
	if s.Public != "" {
		pub := client.MustDecode(s.Public)
		address, err = PubToAddr(pub)
		if err != nil {
			return
		}
	}
	if s.Address != "" {
		vm := client.MustDecode(s.Address)
		address, err = VmAddrToAddr(vm)
		if err != nil {
			return
		}
	}

	entry, err := GetEntry(s.Url, address)
	if err != nil {
		return
	}

	DisplayEntry(entry)

	return nil
}

type respBody struct {
	Data string
	Link string
	Head string
}

func GetEntry(url, address string) (*EvmEntry, error) {
	resp, err := http.Get(url + "/state/" + address)
	if err != nil {
		return nil, err
	}

	body, err := ParseRespBody(resp)
	if err != nil {
		return nil, err
	}

	buf, err := base64.StdEncoding.DecodeString(body.Data)
	if err != nil {
		return nil, err
	}

	entry := &EvmEntry{}
	err = proto.Unmarshal(buf, entry)
	if err != nil {
		return nil, err
	}

	return entry, nil
}

func DisplayEntry(entry *EvmEntry) {
	if entry == nil {
		fmt.Println("Entry is nil")
		return
	}

	act := entry.GetAccount()
	stg := entry.GetStorage()

	if len(act.GetAddress()) == 0 {
		fmt.Println("Account does not exist")
		return
	}

	fmt.Printf(`
Address: %v
Balance: %v
Code   : %v
Nonce  : %v
`, client.MustEncode(act.GetAddress()[:20]), act.GetBalance(), client.MustEncode(act.GetCode()), act.GetNonce())

	if len(stg) == 0 {
		fmt.Println("(No Storage Set)\n")
		return
	}

	fmt.Println("Storage:")
	for _, pair := range stg {
		key := client.MustEncode(pair.GetKey())
		val := client.MustEncode(pair.GetValue())
		fmt.Printf("%v -> %v", key, val)
	}
	fmt.Println("")
}
