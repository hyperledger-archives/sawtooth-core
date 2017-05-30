package burrow_evm_client

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
)

type RespBody struct {
	Data  string
	Link  string
	Head  string
	Error ErrorBody
}

func (r *RespBody) String() string {
	return fmt.Sprintf(`
Data: %v
Link: %v
Head: %v
`, r.Data, r.Link, r.Head)
}

type ErrorBody struct {
	Code    int
	Title   string
	Message string
}

func (e *ErrorBody) String() string {
	return fmt.Sprintf(`
Code    : %v
Title   : %v
Message : %v
`, e.Code, e.Title, e.Message)
}

func ParseRespBody(resp *http.Response) (*RespBody, error) {
	defer resp.Body.Close()
	buf, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	if len(buf) == 0 {
		return nil, fmt.Errorf("Nothing at that address")
	}

	return ParseBodyData(buf)

}

func ParseBodyData(buf []byte) (*RespBody, error) {
	body := &RespBody{}
	err := json.Unmarshal(buf, body)
	return body, err
}
