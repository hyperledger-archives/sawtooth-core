package main

import (
	"fmt"
	"github.com/jessevdk/go-flags"
	"io/ioutil"
	client "sawtooth_burrow_evm/client"
	sdk "sawtooth_sdk/client"
)

type Create struct {
	Output string `short:"o" long:"out" description:"Name of files to create to store the generated keys and address"`
}

func (c *Create) Name() string {
	return "create"
}

func (c *Create) Register(p *flags.Parser) error {
	_, err := p.AddCommand("create", "Create a new account", "", c)
	return err
}

func (c *Create) Run() error {
	priv, pub, addr, err := gen()
	if err != nil {
		return err
	}

	if c.Output != "" {
		err = write(c.Output+".priv", priv)
		if err != nil {
			return err
		}
		err = write(c.Output+".pub", pub)
		if err != nil {
			return err
		}
		err = write(c.Output+".addr", addr)
		if err != nil {
			return err
		}

	} else {
		fmt.Println(priv)
		fmt.Println(pub)
		fmt.Println(addr)
	}

	return nil
}

func gen() (string, string, string, error) {
	priv := sdk.GenPrivKey()
	pub := sdk.GenPubKey(priv)
	addr, err := client.PubToAddr(pub)
	return sdk.MustEncode(priv), sdk.MustEncode(pub), addr[6 : 6+40], err
}

func write(name, s string) error {
	return ioutil.WriteFile(name, []byte(s+"\n"), 0644)
}
