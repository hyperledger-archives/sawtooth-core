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

package handler

import (
	"crypto/sha512"
	"encoding/hex"
	"sawtooth_sdk/logging"
	"sawtooth_sdk/processor"
	"sawtooth_sdk/protobuf/processor_pb2"
	"strings"
)

var logger *logging.Logger = logging.Get()

type NoopHandler struct {
	namespace string
}

func NewNoopHandler(namespace string) *NoopHandler {
	return &NoopHandler{
		namespace: namespace,
	}
}

const FAMILY_NAME = "noop"

func (self *NoopHandler) FamilyName() string {
	return FAMILY_NAME
}
func (self *NoopHandler) FamilyVersions() []string {
	return []string{"1.0"}
}
func (self *NoopHandler) Namespaces() []string {
	return []string{self.namespace}
}

func (self *NoopHandler) Apply(request *processor_pb2.TpProcessRequest, state *processor.Context) error {
	return nil
}

func Hexdigest(str string) string {
	hash := sha512.New()
	hash.Write([]byte(str))
	hashBytes := hash.Sum(nil)
	return strings.ToLower(hex.EncodeToString(hashBytes))
}
