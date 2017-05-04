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

	"burrow/evm/sha3"
	. "burrow/word256"
)

type FakeAppState struct {
	accounts map[string]*Account
	storage  map[string]Word256
}

func (fas *FakeAppState) GetAccount(addr Word256) *Account {
	account := fas.accounts[addr.String()]
	return account
}

func (fas *FakeAppState) UpdateAccount(account *Account) {
	fas.accounts[account.Address.String()] = account
}

func (fas *FakeAppState) RemoveAccount(account *Account) {
	_, ok := fas.accounts[account.Address.String()]
	if !ok {
		panic(fmt.Sprintf("Invalid account addr: %X", account.Address))
	} else {
		// Remove account
		delete(fas.accounts, account.Address.String())
	}
}

func (fas *FakeAppState) CreateAccount(creator *Account) *Account {
	addr := createAddress(creator)
	account := fas.accounts[addr.String()]
	if account == nil {
		return &Account{
			Address: addr,
			Balance: 0,
			Code:    nil,
			Nonce:   0,
		}
	} else {
		panic(fmt.Sprintf("Invalid account addr: %X", addr))
	}
}

func (fas *FakeAppState) GetStorage(addr Word256, key Word256) Word256 {
	_, ok := fas.accounts[addr.String()]
	if !ok {
		panic(fmt.Sprintf("Invalid account addr: %X", addr))
	}

	value, ok := fas.storage[addr.String()+key.String()]
	if ok {
		return value
	} else {
		return Zero256
	}
}

func (fas *FakeAppState) SetStorage(addr Word256, key Word256, value Word256) {
	_, ok := fas.accounts[addr.String()]
	if !ok {
		panic(fmt.Sprintf("Invalid account addr: %X", addr))
	}

	fas.storage[addr.String()+key.String()] = value
}

// Creates a 20 byte address and bumps the nonce.
func createAddress(creator *Account) Word256 {
	nonce := creator.Nonce
	creator.Nonce += 1
	temp := make([]byte, 32+8)
	copy(temp, creator.Address[:])
	PutInt64BE(temp[32:], nonce)
	return LeftPadWord256(sha3.Sha3(temp)[:20])
}
