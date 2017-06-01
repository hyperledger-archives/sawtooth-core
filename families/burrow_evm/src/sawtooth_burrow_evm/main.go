package main

import (
	"fmt"
	"github.com/jessevdk/go-flags"
	"os"
	burrow_evm "sawtooth_burrow_evm/handler"
	"sawtooth_sdk/logging"
	"sawtooth_sdk/processor"
	"syscall"
)

type Opts struct {
	Verbose []bool `short:"v" long:"verbose" description:"Increase verbosity"`
}

func main() {

	var opts Opts

	logger := logging.Get()

	parser := flags.NewParser(&opts, flags.Default)
	remaining, err := parser.Parse()
	if err != nil {
		if flagsErr, ok := err.(*flags.Error); ok && flagsErr.Type == flags.ErrHelp {
			os.Exit(0)
		} else {
			logger.Errorf("Failed to parse args: %v", err)
			os.Exit(2)
		}
	}
	if len(remaining) > 1 {
		fmt.Println("Must pass one or fewer endpoints")
		os.Exit(2)
	}

	endpoint := "tcp://localhost:40000"
	if len(remaining) == 1 {
		endpoint = remaining[0]
	}

	switch len(opts.Verbose) {
	case 2:
		logger.SetLevel(logging.DEBUG)
	case 1:
		logger.SetLevel(logging.INFO)
	default:
		logger.SetLevel(logging.WARN)
	}

	handler := burrow_evm.NewBurrowEVMHandler()
	processor := processor.NewTransactionProcessor(endpoint)
	processor.AddHandler(handler)
	processor.ShutdownOnSignal(syscall.SIGINT, syscall.SIGTERM)
	err = processor.Start()
	if err != nil {
		logger.Error("Processor stopped: ", err)
	}
}
