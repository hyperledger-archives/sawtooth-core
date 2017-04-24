package main

import (
	"os"
	burrow_evm "sawtooth_burrow_evm/handler"
	"sawtooth_sdk/processor"
)

func main() {
	endpoint := "tcp://localhost:40000"
	if len(os.Args) > 1 {
		endpoint = os.Args[2]
	}

	prefix := burrow_evm.Hexdigest("burrow_evm")[:6]
	handler := burrow_evm.NewBurrowEVMHandler(prefix)
	processor := processor.NewTransactionProcessor(endpoint)
	processor.AddHandler(handler)
	processor.Start()
}
