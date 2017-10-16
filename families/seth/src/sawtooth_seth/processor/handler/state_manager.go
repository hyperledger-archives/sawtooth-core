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
	"fmt"
	"github.com/golang/protobuf/proto"
	"sawtooth_sdk/processor"
	. "sawtooth_seth/common"
	. "sawtooth_seth/protobuf/seth_pb2"
)

// -- AppState --

// StateManager simplifies accessing EVM related data stored in state
type StateManager struct {
	state *processor.Context
}

func NewStateManager(state *processor.Context) *StateManager {
	return &StateManager{
		state: state,
	}
}

// NewEntry creates a new entry in state. If an entry already exists at the
// given address or the entry cannot be created, an error is returned.
func (mgr *StateManager) NewEntry(vmAddress *EvmAddr) (*EvmEntry, error) {
	entry, err := mgr.GetEntry(vmAddress)
	if err != nil {
		return nil, err
	}

	if entry != nil {
		return nil, fmt.Errorf("Address already in use")
	}

	entry = &EvmEntry{
		Account: &EvmStateAccount{
			Address:     vmAddress.Bytes(),
			Balance:     0,
			Code:        make([]byte, 0),
			Nonce:       0,
			Permissions: &EvmPermissions{},
		},
		Storage: make([]*EvmStorage, 0),
	}

	err = mgr.SetEntry(vmAddress, entry)
	if err != nil {
		return nil, err
	}

	return entry, nil
}

// DelEntry removes the given entry from state. An error is returned if the
// entry does not exist.
func (mgr *StateManager) DelEntry(vmAddress *EvmAddr) error {
	entry, err := mgr.GetEntry(vmAddress)
	if err != nil {
		return err
	}
	if entry == nil {
		return fmt.Errorf("Entry does not exist %v", vmAddress)
	}
	err = mgr.SetEntry(vmAddress, &EvmEntry{})
	if err != nil {
		return err
	}
	return nil
}

// GetEntry retrieve the entry from state at the given address. If the entry
// does not exist, nil is returned.
func (mgr *StateManager) GetEntry(vmAddress *EvmAddr) (*EvmEntry, error) {
	address := vmAddress.ToStateAddr()

	// Retrieve the account from global state
	entries, err := mgr.state.GetState([]string{address.String()})
	if err != nil {
		return nil, err
	}
	entryData, exists := entries[address.String()]
	if !exists {
		return nil, nil
	}

	// Deserialize the entry
	entry := &EvmEntry{}
	err = proto.Unmarshal(entryData, entry)
	if err != nil {
		return nil, err
	}

	return entry, nil
}

// MustGetEntry wraps GetEntry and panics if the entry does not exist of there
// is an error.
func (mgr *StateManager) MustGetEntry(vmAddress *EvmAddr) *EvmEntry {
	entry, err := mgr.GetEntry(vmAddress)
	if err != nil {
		panic(fmt.Sprintf(
			"Failed to GetEntry(%v): %v", vmAddress, err,
		))
	}

	if entry == nil {
		panic(fmt.Sprintf(
			"Tried to GetEntry(%v) but nothing exists there", vmAddress,
		))
	}

	return entry
}

// SetEntry writes the entry to the given address. Returns an error if it fails
// to set the address.
func (mgr *StateManager) SetEntry(vmAddress *EvmAddr, entry *EvmEntry) error {
	address := vmAddress.ToStateAddr()

	entryData, err := proto.Marshal(entry)
	if err != nil {
		return err
	}

	// Store the account in global state
	addresses, err := mgr.state.SetState(map[string][]byte{
		address.String(): entryData,
	})
	if err != nil {
		return err
	}

	for _, a := range addresses {
		if a == address.String() {
			return nil
		}
	}
	return fmt.Errorf("Address not set: %v", address)
}

// MustSetEntry wraps set entry and panics if there is an error.
func (mgr *StateManager) MustSetEntry(vmAddress *EvmAddr, entry *EvmEntry) {
	err := mgr.SetEntry(vmAddress, entry)
	if err != nil {
		panic(fmt.Sprintf(
			"Failed to SetEntry(%v, %v): %v", vmAddress, entry, err,
		))
	}
}
