package main

import (
	"fmt"
	"github.com/jessevdk/go-flags"
	"os"
	"sawtooth_sdk/logging"
)

var logger *logging.Logger = logging.Get()

const (
	FAMILY_NAME    = "burrow-evm"
	FAMILY_VERSION = "1.0"
	ENCODING       = "application/protobuf"
	PREFIX         = "a84eda"
)

// All subcommands implement this interface
type Command interface {
	Register(*flags.Parser) error
	Name() string
	Do() error
}

// Opts to the main command
type MainOpts struct {
	Verbose []bool `short:"v" long:"verbose" description:"Set the log level"`
}

func main() {

	var opts MainOpts

	// Create top-level parser
	parser := flags.NewParser(&opts, flags.Default)
	parser.Command.Name = "seth"

	// Add sub-commands
	commands := []Command{
		&Create{},
		&Exec{},
		&Load{},
		&Show{},
	}
	for _, cmd := range commands {
		err := cmd.Register(parser)
		if err != nil {
			logger.Errorf("Couldn't register command %v: %v", cmd.Name(), err)
			os.Exit(1)
		}
	}

	// Parse the args
	remaining, err := parser.Parse()
	if e, ok := err.(*flags.Error); ok {
		if e.Type == flags.ErrHelp {
			return
		} else {
			os.Exit(1)
		}
	}

	if len(remaining) > 0 {
		fmt.Printf("Error: Unrecognized arguments passed: %v\n", remaining)
		os.Exit(2)
	}

	switch len(opts.Verbose) {
	case 2:
		logger.SetLevel(logging.DEBUG)
	case 1:
		logger.SetLevel(logging.INFO)
	default:
		logger.SetLevel(logging.WARN)
	}

	// If a sub-command was passed, run it
	if parser.Command.Active == nil {
		os.Exit(2)
	}

	name := parser.Command.Active.Name
	for _, cmd := range commands {
		if cmd.Name() == name {
			err := cmd.Do()
			if err != nil {
				fmt.Printf("Error: %v\n", err)
				os.Exit(1)
			}
			return
		}
	}
}
