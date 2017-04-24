package messaging

type CreateStreamError struct {
	msg string
}

func (err *CreateStreamError) Error() string {
	return err.msg
}

type SendMsgError struct {
	msg string
}

func (err *SendMsgError) Error() string {
	return err.msg
}

type RecvMsgError struct {
	msg string
}

func (err *RecvMsgError) Error() string {
	return err.msg
}
