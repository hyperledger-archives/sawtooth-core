package main

import (
	"fmt"
	"github.com/jessevdk/go-flags"
	client "sawtooth_burrow_evm/client"
	. "sawtooth_burrow_evm/protobuf/evm_pb2"
	sdk "sawtooth_sdk/client"
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
	_, err := p.AddCommand("show", "Show all data associated with a given account", "", s)
	return err
}

func (s *Show) Run() (err error) {
	client := client.New(s.Url)

	// Make sure only one was passed
	n := 0
	args := []string{s.Private, s.Public, s.Address}
	for _, a := range args {
		if a != "" {
			n += 1
		}
	}
	if n != 1 {
		return fmt.Errorf("Must pass exactly one of {-k PRIVATE, -p PUBLIC, -a ADDRESS}")
	}

	var entry *EvmEntry
	if s.Private != "" {
		priv := sdk.MustDecode(s.Private)
		entry, err = client.GetEntry(priv, "private")
	}
	if s.Public != "" {
		pub := sdk.MustDecode(s.Public)
		entry, err = client.GetEntry(pub, "public")
	}
	if s.Address != "" {
		vm := sdk.MustDecode(s.Address)
		entry, err = client.GetEntry(vm, "address")
	}
	if err != nil {
		return
	}

	DisplayEntry(entry)

	return nil
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
`, sdk.MustEncode(act.GetAddress()[:20]), act.GetBalance(), sdk.MustEncode(act.GetCode()), act.GetNonce())

	if len(stg) == 0 {
		fmt.Println("(No Storage Set)\n")
		return
	}

	fmt.Println("Storage:")
	for _, pair := range stg {
		key := sdk.MustEncode(pair.GetKey())
		val := sdk.MustEncode(pair.GetValue())
		fmt.Printf("%v -> %v\n", key, val)
	}
	fmt.Println("")
}
