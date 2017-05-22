package handler

import (
	. "burrow/evm"
	"burrow/evm/sha3"
	. "burrow/word256"
	"fmt"
	. "sawtooth_burrow_evm/protobuf/evm_pb2"
)

// -- AppState --

type SawtoothAppState struct {
	mgr *StateManager
}

func NewSawtoothAppState(mgr *StateManager) *SawtoothAppState {
	return &SawtoothAppState{
		mgr: mgr,
	}
}

// GetAccount retrieves an existing account with the given address. Panics if
// the account doesn't exist.
func (s *SawtoothAppState) GetAccount(vmAddress Word256) *Account {
	logger.Debugf("GetAccount(%v)", vmAddress)

	entry := s.mgr.MustGetEntry(vmAddress.Bytes())

	return toVmAccount(entry.GetAccount())
}

// UpdateAccount updates the account in state. Panics if the account doesn't
// exist.
func (s *SawtoothAppState) UpdateAccount(vmAccount *Account) {
	logger.Debugf("UpdateAccount(%v)", vmAccount)
	address := vmAccount.Address.Bytes()

	entry := s.mgr.MustGetEntry(vmAccount.Address.Bytes())

	entry.Account = toStateAccount(vmAccount)

	s.mgr.MustSetEntry(address, entry)
}

// RemoveAccount removes the account and associated storage from global state
// and panics if it doesn't exist.
func (s *SawtoothAppState) RemoveAccount(vmAccount *Account) {
	logger.Debugf("RemoveAccount(%v)")
	address := vmAccount.Address.Bytes()
	err := s.mgr.DelEntry(address)
	if err != nil {
		panic(fmt.Sprintf(
			"Tried to DelEntry(%v) but nothing exists there", address,
		))
	}
}

// CreateAccount creates a new Contract Account using the given existing
// account to generate a new address. panics if the given account doesn't exist
// or the address of the newly created account conflicts with an existing
// account.
func (s *SawtoothAppState) CreateAccount(creator *Account) *Account {
	logger.Debugf("CreateAccount(%v)", creator)

	// Get address of new account
	address := deriveNewVmAddress(creator).Bytes()

	// If it already exists, something has gone wrong
	entry, err := s.mgr.NewEntry(address)
	if err != nil {
		panic(fmt.Sprintf(
			"Failed to NewEntry(%v)", address,
		))
	}

	return toVmAccount(entry.GetAccount())
}

// GetStorage gets the 256 bit value stored with the given key in the given
// account. panics if the account and key do not both exist.
func (s *SawtoothAppState) GetStorage(address, key Word256) Word256 {
	logger.Debugf("GetStorage(%v, %v)", address, key)

	// Load the entry from global state
	entry := s.mgr.MustGetEntry(address.Bytes())

	storage := entry.GetStorage()

	for _, pair := range storage {
		k := LeftPadWord256(pair.GetKey())
		if k.Compare(key) == 0 {
			return LeftPadWord256(pair.GetValue())
		}
	}

	panic(fmt.Sprint(
		"Key %v not set for account %v", key.Bytes(), address.Bytes(),
	))
}

func (s *SawtoothAppState) SetStorage(address, key, value Word256) {
	logger.Debugf("SetStorage(%v, %v, %v)", address, key, value)

	entry := s.mgr.MustGetEntry(address.Bytes())

	// Make sure we update the entry after changing it
	defer func() {
		s.mgr.MustSetEntry(address.Bytes(), entry)
	}()

	storage := entry.GetStorage()
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

// Creates a 20 byte address and bumps the nonce.
func deriveNewVmAddress(sender *Account) Word256 {
	buf := make([]byte, Word256Length+8)
	copy(buf, sender.Address.Bytes())
	PutInt64BE(buf[Word256Length:], sender.Nonce)
	return createVmAddress(buf)
}

func createVmAddress(b []byte) Word256 {
	return RightPadWord256(sha3.Sha3(b)[:20])
}

func toStateAccount(a *Account) *EvmStateAccount {
	return &EvmStateAccount{
		Address: a.Address.Bytes(),
		Balance: a.Balance,
		Code:    a.Code,
		Nonce:   a.Nonce,
	}
}

func toVmAccount(sa *EvmStateAccount) *Account {
	return &Account{
		Address: RightPadWord256(sa.Address),
		Balance: sa.Balance,
		Code:    sa.Code,
		Nonce:   sa.Nonce,
	}
}
