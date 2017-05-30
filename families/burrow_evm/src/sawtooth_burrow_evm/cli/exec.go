package main

import (
	"fmt"
	"github.com/jessevdk/go-flags"
	client "sawtooth_burrow_evm/client"
	sdk "sawtooth_sdk/client"
)

type Exec struct {
	Private string `short:"k" long:"key" required:"true" description:"A hex encoded private key to make the message call with."`
	To      string `short:"t" long:"to" required:"true" description:"A 160 bit hex encoded address of an account to call."`
	Data    string `short:"d" long:"data" description:"Hex encoded data to call the account with."`
	Url     string `short:"U" long:"url" description:"The REST API URL to connect to when sending the transaction." default:"http://127.0.0.1:8080"`
	Gas     uint64 `short:"g" long:"gas" description:"Amount of gas to supply the transaction with." default:"1000"`
}

func (e *Exec) Name() string {
	return "exec"
}

func (e *Exec) Register(p *flags.Parser) error {
	_, err := p.AddCommand("exec", "Call an existing account", "", e)
	return err
}

func (e *Exec) Run() error {
	client := client.New(e.Url)

	priv := sdk.Decode(e.Private, "hex")
	to := sdk.Decode(e.To, "hex")
	data := sdk.Decode(e.Data, "hex")

	response, err := client.Exec(priv, to, data, e.Gas)
	if err != nil {
		return err
	}

	fmt.Println(response)
	return nil
}
