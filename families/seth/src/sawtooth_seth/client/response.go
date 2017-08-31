/**
 * Copyright 2017 Intel Corporation
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * ------------------------------------------------------------------------------
 */

package client

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
)

type RespBody struct {
	Data  interface{}
	Link  string
	Head  string
	Error ErrorBody
}

func (r *RespBody) String() string {
	if r.Data == nil {
		return fmt.Sprintf(`
Data:
Link: %v
Head: %v
		`, r.Link, r.Head)
	}
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

func (e *ErrorBody) Error() string {
	return e.String()
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
