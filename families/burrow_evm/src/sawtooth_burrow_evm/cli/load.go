package main

import (
	"fmt"
	"github.com/jessevdk/go-flags"
	client "sawtooth_burrow_evm/client"
	sdk "sawtooth_sdk/client"
)

type Load struct {
	Private string `short:"k" long:"key" required:"true" description:"A hex encoded private key to create the account with. See 'sawtooth keygen' for creation."`
	Init    string `short:"i" long:"init" description:"Hex encoded initialization code to run on account creation."`
	Url     string `short:"U" long:"url" description:"The REST API URL to connect to when sending the transaction." default:"http://127.0.0.1:8080"`
	Gas     uint64 `short:"g" long:"gas" description:"Amount of gas to supply the transaction with." default:"1000"`
}

func (c *Load) Name() string {
	return "load"
}

func (c *Load) Register(p *flags.Parser) error {
	_, err := p.AddCommand("load", "Load a new account into state", "", c)
	return err
}

func (c *Load) Run() error {
	client := client.New(c.Url)

	priv := sdk.Decode(c.Private, "hex")
	init := sdk.Decode(c.Init, "hex")

	response, err := client.Load(priv, init, c.Gas)
	if err != nil {
		return err
	}

	fmt.Println(response)
	return nil
}
