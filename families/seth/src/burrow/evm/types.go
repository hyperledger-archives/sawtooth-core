// Copyright 2017 Monax Industries Limited
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//    http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package vm

import (
	"fmt"

	ptypes "burrow/permission/types"
	. "burrow/word256"
)

const (
	defaultDataStackCapacity = 10
)

type Account struct {
	Address Word256
	Balance int64
	Code    []byte
	Nonce   int64
	Other   interface{} // For holding all other data.

	Permissions ptypes.AccountPermissions
}

func (acc *Account) String() string {
	if acc == nil {
		return "nil-VMAccount"
	}
	return fmt.Sprintf("VMAccount{%X B:%v C:%X N:%v}",
		acc.Address, acc.Balance, acc.Code, acc.Nonce)
}

type AppState interface {

	// Accounts
	GetAccount(addr Word256) *Account
	UpdateAccount(*Account)
	RemoveAccount(*Account)
	CreateAccount(*Account) *Account

	// Storage
	GetStorage(Word256, Word256) Word256
	SetStorage(Word256, Word256, Word256) // Setting to Zero is deleting.

	// State
	GetBlockHash(int64) (Word256, error)
}

type Params struct {
	BlockHeight int64
	BlockHash   Word256
	BlockTime   int64
	GasLimit    int64
}

type EventFireable interface {
	FireEvent(string, EventDataLog) (error)
}

type EventDataLog struct {
	Address     Word256
	Topics      []Word256
	Data        []byte
	BlockHeight int64
}
