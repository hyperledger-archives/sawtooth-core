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
