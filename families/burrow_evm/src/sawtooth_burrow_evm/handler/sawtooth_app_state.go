package handler

import (
	. "burrow/evm"
	"burrow/evm/sha3"
	. "burrow/word256"
	"github.com/golang/protobuf/proto"
	"sawtooth_sdk/processor"
	. "sawtooth_sdk/protobuf/evm_pb2"
)

// Ideas:
// - May want to preload certain addresses/accounts.
// - Probably want to cache accounts/storage if the EVM will be accessing them
//   frequently.

// TODO: Replace "return nil" with error handling/panic

// -- AppState --

type SawtoothAppState struct {
	namespace string
	state     *processor.State
	//cache map[Word256]*EvmEntry
}

func NewSawtoothAppState(namespace string, state *processor.State) *SawtoothAppState {
	return &SawtoothAppState{
		namespace: namespace,
		state:     state,
		//cache: make(map[Word256]*EvmEntry)
	}
}

// Load the entry from global state
func (self *SawtoothAppState) GetAccount(address Word256) *Account {
	logger.Debugf("GetAccount(%v)", address)
	entry := getEntry(self.state, self.namespace, address)

	stateAccount := entry.GetAccount()
	if stateAccount == nil {
		panic("No account at address: " + address.String())
	}

	account := toVmAccount(stateAccount)

	return account
}

// Update the account in global state
func (self *SawtoothAppState) UpdateAccount(account *Account) {
	logger.Debugf("UpdateAccount(%v)", account)
	entry := getEntry(self.state, self.namespace, account.Address)

	entry.Account = toStateAccount(account)

	setEntry(self.state, self.namespace, account.Address, entry)
}

// Delete the account from global state, panic if it doesn't exist
func (self *SawtoothAppState) RemoveAccount(account *Account) {
	logger.Debugf("RemoveAccount(%v)")
	entry := getEntry(self.state, self.namespace, account.Address)

	entry.Account = nil

	setEntry(self.state, self.namespace, account.Address, entry)
}

// Create a new account in global state using the given account and return
// it. panic if the address already exists.
func (self *SawtoothAppState) CreateAccount(creator *Account) *Account {
	// TODO: Should this store the newly created account in state, or does the EVM
	// do that by calling UpdateAccount later?
	logger.Debugf("CreateAccount(%v)", creator)

	// Create address of new account
	newAddress := createAddress(creator)

	// If it already exists, something has gone wrong
	if getEntry(self.state, self.namespace, newAddress) != nil {
		panic("Account already exists!")
	}

	return &Account{
		Address: newAddress,
		Balance: 0,
		Code:    nil,
		Nonce:   0,
	}
}

// Get value stored at address+key in storage
func (self *SawtoothAppState) GetStorage(address, key Word256) Word256 {
	logger.Debugf("GetStorage(%v, %v)", address, key)
	// Load the entry from global state
	entry := getEntry(self.state, self.namespace, address)

	storage := entry.GetStorage()
	if storage == nil {
		panic("No account at address: " + address.String())
	}

	pairs := make(map[Word256]Word256)
	for _, pair := range storage {
		k := Int64ToWord256(pair.GetKey())
		v := Int64ToWord256(pair.GetValue())
		pairs[k] = v
	}

	value, exists := pairs[key]
	if !exists {
		panic("Nothing stored at " + address.String() + ":" + key.String())
	}

	return value
}

func (self *SawtoothAppState) SetStorage(address, key, value Word256) {
	logger.Debugf("SetStorage(%v, %v, %v)", address, key, value)
	// Set storage at address+key to val
	entry := getEntry(self.state, self.namespace, address)

	storage := entry.GetStorage()
	if storage == nil {
		panic("No account at address: " + address.String())
	}

	pairs := make(map[Word256]Word256)
	for _, pair := range storage {
		k := Int64ToWord256(pair.GetKey())
		v := Int64ToWord256(pair.GetValue())
		pairs[k] = v
	}

	pairs[key] = value

	newStorage := make([]*EvmStorage, 0, len(pairs))
	for k, v := range pairs {
		newStorage = append(newStorage, &EvmStorage{
			Key:   Int64FromWord256(k),
			Value: Int64FromWord256(v),
		})
	}

	entry.Storage = newStorage

	setEntry(self.state, self.namespace, address, entry)
}

// -- Caching --

//type CacheEvmEntry struct {
//EvmEntry EvmEvmEntry
//Modified bool
//}

//func (self *SawtoothAppState) Sync() {
//// Send Set Requests to update all change data in the cache
//}

// -- Utilities --

// Creates a 20 byte address and bumps the nonce.
func createAddress(creator *Account) Word256 {
	nonce := creator.Nonce
	creator.Nonce += 1
	temp := make([]byte, 32+8)
	copy(temp, creator.Address[:])
	PutInt64BE(temp[32:], nonce)
	return LeftPadWord256(sha3.Sha3(temp)[:20])
}

func getEntry(state *processor.State, prefix string, address Word256) *EvmEntry {
	// Construct full address
	fullAddress := prefix + address.String()

	// Retrieve the account from global state
	entries, err := state.Get([]string{fullAddress})
	if err != nil {
		panic(err)
	}
	entryData, exists := entries[fullAddress]
	if !exists {
		return nil
	}

	// Deserialize the entry
	entry := &EvmEntry{}
	err = proto.Unmarshal(entryData, entry)
	if err != nil {
		panic(err)
	}

	return entry
}

func setEntry(state *processor.State, prefix string, address Word256, entry *EvmEntry) {
	// Construct full address
	fullAddress := prefix + address.String()

	entryData, err := proto.Marshal(entry)
	if err != nil {
		panic(err)
	}

	// Store the account in global state
	addresses, err := state.Set(map[string][]byte{
		fullAddress: entryData,
	})
	if err != nil {
		panic(err)
	}

	for _, address := range addresses {
		if address == fullAddress {
			return
		}
	}
	panic("Address not set: " + fullAddress)
}

func toStateAccount(a *Account) *EvmStateAccount {
	return &EvmStateAccount{
		Address: Int64FromWord256(a.Address),
		Balance: a.Balance,
		Code:    a.Code,
		Nonce:   a.Nonce,
	}
}

func toVmAccount(sa *EvmStateAccount) *Account {
	return &Account{
		Address: Int64ToWord256(sa.Address),
		Balance: sa.Balance,
		Code:    sa.Code,
		Nonce:   sa.Nonce,
	}
}
