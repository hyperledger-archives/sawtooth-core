package burrow_evm_client

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
)

type RespBody struct {
	Data string
	Link string
	Head string
}

func (r *RespBody) String() string {
	return fmt.Sprintf(`
Data: %v
Link: %v
Head: %v
`, r.Data, r.Link, r.Head)
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

	body := &RespBody{}
	err = json.Unmarshal(buf, body)

	return body, err
}
