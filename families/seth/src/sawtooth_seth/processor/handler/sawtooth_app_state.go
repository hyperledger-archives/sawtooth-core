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
	. "burrow/evm"
	ptypes "burrow/permission/types"
	. "burrow/word256"
	"fmt"
	"sawtooth_sdk/processor"
	. "sawtooth_seth/common"
	. "sawtooth_seth/protobuf/seth_pb2"
)

// -- AppState --

// SawtoothAppState implements the interface used by the Burrow EVM to
// access global state
type SawtoothAppState struct {
	mgr *StateManager
}

func NewSawtoothAppState(state *processor.Context) *SawtoothAppState {
	return &SawtoothAppState{
		mgr: NewStateManager(state),
	}
}

// GetAccount retrieves an existing account with the given address. Returns nil
// if the account doesn't exist.
func (s *SawtoothAppState) GetAccount(addr Word256) *Account {
	vmAddress, err := NewEvmAddrFromBytes(addr.Bytes()[:20])
	if err != nil {
		panic(err.Error())
	}
	logger.Debugf("GetAccount(%v)", vmAddress)

	entry, err := s.mgr.GetEntry(vmAddress)
	if err != nil {
		panic(err.Error())
	}
	if entry == nil {
		return nil
	}

	return toVmAccount(entry.GetAccount())
}

// UpdateAccount updates the account in state. Creates the account if it doesn't
// exist yet.
func (s *SawtoothAppState) UpdateAccount(acct *Account) {
	vmAddress, err := NewEvmAddrFromBytes(acct.Address.Bytes()[:20])
	if err != nil {
		panic(err.Error())
	}
	logger.Debugf("UpdateAccount(%v)", vmAddress)

	entry, err := s.mgr.GetEntry(vmAddress)
	if err != nil {
		panic(err.Error())
	}
	if entry == nil {
		entry, err = s.mgr.NewEntry(vmAddress)
		if err != nil {
			panic(err.Error())
		}
	}

	entry.Account = toStateAccount(acct)

	s.mgr.MustSetEntry(vmAddress, entry)
}

// RemoveAccount removes the account and associated storage from global state
// and panics if it doesn't exist.
func (s *SawtoothAppState) RemoveAccount(acct *Account) {
	vmAddress, err := NewEvmAddrFromBytes(acct.Address.Bytes()[:20])
	if err != nil {
		panic(err.Error())
	}
	logger.Debugf("RemoveAccount(%v)", vmAddress)

	err = s.mgr.DelEntry(vmAddress)
	if err != nil {
		panic(fmt.Sprintf(
			"Tried to DelEntry(%v) but nothing exists there", vmAddress,
		))
	}
}

// CreateAccount creates a new Contract Account using the given existing
// account to generate a new address. panics if the given account doesn't exist
// or the address of the newly created account conflicts with an existing
// account.
func (s *SawtoothAppState) CreateAccount(creator *Account) *Account {
	creatorAddress, err := NewEvmAddrFromBytes(creator.Address.Bytes()[:20])
	if err != nil {
		panic(err.Error())
	}
	logger.Debugf("CreateAccount(%v)", creatorAddress)

	// Get address of new account
	newAddress := creatorAddress.Derive(uint64(creator.Nonce))

	// Increment nonce
	creator.Nonce += 1

	// If it already exists, something has gone wrong
	entry, err := s.mgr.NewEntry(newAddress)
	if err != nil {
		panic(fmt.Sprintf(
			"Failed to NewEntry(%v): %v", newAddress, err.Error(),
		))
	}

	return toVmAccount(entry.GetAccount())
}

// GetStorage gets the 256 bit value stored with the given key in the given
// account. panics if the account and key do not both exist.
func (s *SawtoothAppState) GetStorage(address, key Word256) Word256 {
	vmAddress, err := NewEvmAddrFromBytes(address.Bytes()[:20])
	if err != nil {
		panic(err.Error())
	}
	logger.Debugf("GetStorage(%v, %v)", vmAddress, key.Bytes())

	// Load the entry from global state
	entry := s.mgr.MustGetEntry(vmAddress)

	storage := entry.GetStorage()

	for _, pair := range storage {
		k := LeftPadWord256(pair.GetKey())
		if k.Compare(key) == 0 {
			return LeftPadWord256(pair.GetValue())
		}
	}

	panic(fmt.Sprint(
		"Key %v not set for account %v", key.Bytes(), vmAddress,
	))
}

func (s *SawtoothAppState) SetStorage(address, key, value Word256) {
	vmAddress, err := NewEvmAddrFromBytes(address.Bytes()[:20])
	if err != nil {
		panic(err.Error())
	}
	logger.Debugf("SetStorage(%v, %v, %v)", vmAddress, key.Bytes(), value.Bytes())

	entry := s.mgr.MustGetEntry(vmAddress)

	storage := entry.GetStorage()

	// Make sure we update the entry after changing it
	defer func() {
		entry.Storage = storage
		logger.Debugf("Storage")
		for _, pair := range entry.GetStorage() {
			logger.Debugf("%v -> %v", pair.GetKey(), pair.GetValue())
		}
		s.mgr.MustSetEntry(vmAddress, entry)
	}()

	for _, pair := range storage {
		k := LeftPadWord256(pair.GetKey())

		// If the key has already been set, overwrite it
		if k.Compare(key) == 0 {
			pair.Value = value.Bytes()
			return
		}
	}

	// If the key is new, append it
	storage = append(storage, &EvmStorage{
		Key:   key.Bytes(),
		Value: value.Bytes(),
	})
}

// -- Utilities --

func toStateAccount(acct *Account) *EvmStateAccount {
	if acct == nil {
		return nil
	}
	return &EvmStateAccount{
		Address:     acct.Address.Bytes()[:20],
		Balance:     acct.Balance,
		Code:        acct.Code,
		Nonce:       acct.Nonce,
		Permissions: toStatePermissions(acct.Permissions),
	}
}

func toVmAccount(sa *EvmStateAccount) *Account {
	if sa == nil {
		return nil
	}
	return &Account{
		Address:     RightPadWord256(sa.Address),
		Balance:     sa.Balance,
		Code:        sa.Code,
		Nonce:       sa.Nonce,
		Permissions: toVmPermissions(sa.Permissions),
	}
}

func toStatePermissions(aPerm ptypes.AccountPermissions) *EvmPermissions {
	return &EvmPermissions{
		Perms:  uint64(aPerm.Base.Perms),
		SetBit: uint64(aPerm.Base.SetBit),
	}
}

func toVmPermissions(ePerm *EvmPermissions) ptypes.AccountPermissions {
	return ptypes.AccountPermissions{
		Base: ptypes.BasePermissions{
			Perms:  ptypes.PermFlag(ePerm.Perms),
			SetBit: ptypes.PermFlag(ePerm.SetBit),
		},
	}
}
