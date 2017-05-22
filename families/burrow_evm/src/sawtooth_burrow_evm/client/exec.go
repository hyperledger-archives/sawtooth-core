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

func (e *Exec) Do() error {
	priv := client.MustDecode(e.Private)
	to := client.MustDecode(e.To)
	data := client.MustDecode(e.Data)

	transaction := &EvmTransaction{
		GasLimit: e.Gas,
		Data:     data,
		To:       to,
	}

	fromAddr, err := PrivToAddr(priv)
	toAddr, err := VmAddrToAddr(to)
	if err != nil {
		return err
	}

	encoder := client.NewEncoder(priv, client.TransactionParams{
		FamilyName:      FAMILY_NAME,
		FamilyVersion:   FAMILY_VERSION,
		PayloadEncoding: ENCODING,
		Inputs:          []string{fromAddr, toAddr},
		Outputs:         []string{fromAddr, toAddr},
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
		e.Url+"/batches", "application/octet-stream", buf,
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
