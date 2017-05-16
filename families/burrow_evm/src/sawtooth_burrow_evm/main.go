package main

import (
	"flag"
	burrow_evm "sawtooth_burrow_evm/handler"
	"sawtooth_sdk/logging"
	"sawtooth_sdk/processor"
	"syscall"
)

func main() {
	v := flag.Bool("v", false, "Info level logging")
	vv := flag.Bool("vv", false, "Debug level logging")
	endpoint := "tcp://localhost:40000"

	flag.Parse()
	args := flag.Args()
	if len(args) > 0 {
		// Overwrite the default endpoint if specified
		endpoint = args[0]
	}

	level := logging.WARN
	if *v {
		level = logging.INFO
	}
	if *vv {
		level = logging.DEBUG
	}

	logger := logging.Get()
	logger.SetLevel(level)

	prefix := burrow_evm.Hexdigest("burrow_evm")[:6]
	handler := burrow_evm.NewBurrowEVMHandler(prefix)
	processor := processor.NewTransactionProcessor(endpoint)
	processor.AddHandler(handler)
	processor.ShutdownOnSignal(syscall.SIGINT, syscall.SIGTERM)
	err := processor.Start()
	if err != nil {
		logger.Error("Processor stopped: ", err)
	}
}
