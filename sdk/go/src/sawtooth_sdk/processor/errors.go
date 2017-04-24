package processor

import "fmt"

type GetError struct {
	Msg string
}

func (err *GetError) Error() string {
	return err.Msg
}

type SetError struct {
	Msg string
}

func (err *SetError) Error() string {
	return err.Msg
}

type UnknownHandlerError struct {
	Msg string
}

func (err *UnknownHandlerError) Error() string {
	return err.Msg
}

type RegistrationError struct {
	Msg string
}

func (err *RegistrationError) Error() string {
	return fmt.Sprint("Failed to register: ", err.Msg)
}

type InvalidTransactionError struct {
	Msg string
}

func (err *InvalidTransactionError) Error() string {
	return fmt.Sprint("Invalid transaction: ", err.Msg)
}

type InternalError struct {
	Msg string
}

func (err *InternalError) Error() string {
	return fmt.Sprint("Internal error: ", err.Msg)
}
