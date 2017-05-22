package main

import (
	"bytes"
	"fmt"
	"github.com/golang/protobuf/proto"
	"github.com/jessevdk/go-flags"
	"net/http"
	. "sawtooth_burrow_evm/protobuf/evm_pb2"
	"sawtooth_sdk/client"
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

func (c *Load) Do() error {
	priv := client.MustDecode(c.Private)

	init := client.MustDecode(c.Init)

	transaction := &EvmTransaction{
		GasLimit: c.Gas,
		Init:     init,
	}

	address, err := PrivToAddr(priv)
	if err != nil {
		return err
	}

	encoder := client.NewEncoder(priv, client.TransactionParams{
		FamilyName:      FAMILY_NAME,
		FamilyVersion:   FAMILY_VERSION,
		PayloadEncoding: ENCODING,
		Inputs:          []string{address},
		Outputs:         []string{address},
	})

	payload, err := proto.Marshal(transaction)
	if err != nil {
		return fmt.Errorf("Couldn't serialize transaction: %v", err)
	}

	txn := encoder.NewTransaction(payload, client.TransactionParams{})
	batch := encoder.NewBatch([]*client.Transaction{txn})
	b := client.SerializeBatches([]*client.Batch{batch})

	buf := bytes.NewReader(b)

	resp, err := http.Post(
		c.Url+"/batches", "application/octet-stream", buf,
	)

	if err != nil {
		return fmt.Errorf("Couldn't send transaction: %v", err)
	}

	body, err := ParseRespBody(resp)
	if err != nil {
		return fmt.Errorf("Couldn't parse response")
	}
	fmt.Println(body)

	return nil
}
