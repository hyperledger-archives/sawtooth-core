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

	"burrow/common/sanity"
	"burrow/evm/sha3"
	ptypes "burrow/permission/types"
	. "burrow/word256"

	"strings"

	"burrow/evm/abi"
)

//
// SNative (from 'secure natives') are native (go) contracts that are dispatched
// based on account permissions and can access and modify an account's permissions
//

// Metadata for SNative contract. Acts as a call target from the EVM. Can be
// used to generate bindings in a smart contract languages.
type SNativeContractDescription struct {
	// Comment describing purpose of SNative contract and reason for assembling
	// the particular functions
	Comment string
	// Name of the SNative contract
	Name          string
	functionsByID map[abi.FunctionSelector]*SNativeFunctionDescription
	functions     []*SNativeFunctionDescription
}

// Metadata for SNative functions. Act as call targets for the EVM when
// collected into an SNativeContractDescription. Can be used to generate
// bindings in a smart contract languages.
type SNativeFunctionDescription struct {
	// Comment describing function's purpose, parameters, and return value
	Comment string
	// Function name (used to form signature)
	Name string
	// Function arguments (used to form signature)
	Args []abi.Arg
	// Function return value
	Return abi.Return
	// Permissions required to call function
	PermFlag ptypes.PermFlag
	// Native function to which calls will be dispatched when a containing
	// contract is called with a FunctionSelector matching this NativeContract
	F NativeContract
}

func registerSNativeContracts() {
	for _, contract := range SNativeContracts() {
		registeredNativeContracts[contract.AddressWord256()] = contract.Dispatch
	}
}

// Returns a map of all SNative contracts defined indexed by name
func SNativeContracts() map[string]*SNativeContractDescription {
	permFlagTypeName := abi.Uint64TypeName
	roleTypeName := abi.Bytes32TypeName
	contracts := []*SNativeContractDescription{
		NewSNativeContract(`
		* Interface for managing Secure Native authorizations.
		* @dev This interface describes the functions exposed by the SNative permissions layer in burrow.
		`,
			"Permissions",
			&SNativeFunctionDescription{`
			* @notice Adds a role to an account
			* @param _account account address
			* @param _role role name
			* @return result whether role was added
			`,
				"addRole",
				[]abi.Arg{
					arg("_account", abi.AddressTypeName),
					arg("_role", roleTypeName),
				},
				ret("result", abi.BoolTypeName),
				ptypes.AddRole,
				addRole},

			&SNativeFunctionDescription{`
			* @notice Removes a role from an account
			* @param _account account address
			* @param _role role name
			* @return result whether role was removed
			`,
				"removeRole",
				[]abi.Arg{
					arg("_account", abi.AddressTypeName),
					arg("_role", roleTypeName),
				},
				ret("result", abi.BoolTypeName),
				ptypes.RmRole,
				removeRole},

			&SNativeFunctionDescription{`
			* @notice Indicates whether an account has a role
			* @param _account account address
			* @param _role role name
			* @return result whether account has role
			`,
				"hasRole",
				[]abi.Arg{
					arg("_account", abi.AddressTypeName),
					arg("_role", roleTypeName),
				},
				ret("result", abi.BoolTypeName),
				ptypes.HasRole,
				hasRole},

			&SNativeFunctionDescription{`
			* @notice Sets the permission flags for an account. Makes them explicitly set (on or off).
			* @param _account account address
			* @param _permission the base permissions flags to set for the account
			* @param _set whether to set or unset the permissions flags at the account level
			* @return result the effective permissions flags on the account after the call
			`,
				"setBase",
				[]abi.Arg{
					arg("_account", abi.AddressTypeName),
					arg("_permission", permFlagTypeName),
					arg("_set", abi.BoolTypeName),
				},
				ret("result", permFlagTypeName),
				ptypes.SetBase,
				setBase},

			&SNativeFunctionDescription{`
			* @notice Unsets the permissions flags for an account. Causes permissions being unset to fall through to global permissions.
      * @param _account account address
      * @param _permission the permissions flags to unset for the account
			* @return result the effective permissions flags on the account after the call
      `,
				"unsetBase",
				[]abi.Arg{
					arg("_account", abi.AddressTypeName),
					arg("_permission", permFlagTypeName)},
				ret("result", permFlagTypeName),
				ptypes.UnsetBase,
				unsetBase},

			&SNativeFunctionDescription{`
			* @notice Indicates whether an account has a subset of permissions set
			* @param _account account address
			* @param _permission the permissions flags (mask) to check whether enabled against base permissions for the account
			* @return result whether account has the passed permissions flags set
			`,
				"hasBase",
				[]abi.Arg{
					arg("_account", abi.AddressTypeName),
					arg("_permission", permFlagTypeName)},
				ret("result", permFlagTypeName),
				ptypes.HasBase,
				hasBase},

			&SNativeFunctionDescription{`
			* @notice Sets the global (default) permissions flags for the entire chain
			* @param _permission the permissions flags to set
			* @param _set whether to set (or unset) the permissions flags
			* @return result the global permissions flags after the call
			`,
				"setGlobal",
				[]abi.Arg{
					arg("_permission", permFlagTypeName),
					arg("_set", abi.BoolTypeName)},
				ret("result", permFlagTypeName),
				ptypes.SetGlobal,
				setGlobal},
		),
	}

	contractMap := make(map[string]*SNativeContractDescription, len(contracts))
	for _, contract := range contracts {
		if _, ok := contractMap[contract.Name]; ok {
			// If this happens we have a pseudo compile time error that will be caught
			// on native.go init()
			panic(fmt.Errorf("Duplicate contract with name %s defined. "+
				"Contract names must be unique.", contract.Name))
		}
		contractMap[contract.Name] = contract
	}
	return contractMap
}

// Create a new SNative contract description object by passing a comment, name
// and a list of member functions descriptions
func NewSNativeContract(comment, name string,
	functions ...*SNativeFunctionDescription) *SNativeContractDescription {

	functionsByID := make(map[abi.FunctionSelector]*SNativeFunctionDescription, len(functions))
	for _, f := range functions {
		fid := f.ID()
		otherF, ok := functionsByID[fid]
		if ok {
			panic(fmt.Errorf("Function with ID %x already defined: %s", fid,
				otherF))
		}
		functionsByID[fid] = f
	}
	return &SNativeContractDescription{
		Comment:       comment,
		Name:          name,
		functionsByID: functionsByID,
		functions:     functions,
	}
}

// This function is designed to be called from the EVM once a SNative contract
// has been selected. It is also placed in a registry by registerSNativeContracts
// So it can be looked up by SNative address
func (contract *SNativeContractDescription) Dispatch(appState AppState,
	caller *Account, args []byte, gas *int64) (output []byte, err error) {
	if len(args) < abi.FunctionSelectorLength {
		return nil, fmt.Errorf("SNatives dispatch requires a 4-byte function "+
			"identifier but arguments are only %s bytes long", len(args))
	}

	function, err := contract.FunctionByID(firstFourBytes(args))
	if err != nil {
		return nil, err
	}

	remainingArgs := args[abi.FunctionSelectorLength:]

	// check if we have permission to call this function
	if !HasPermission(appState, caller, function.PermFlag) {
		return nil, ErrInvalidPermission{caller.Address, function.Name}
	}

	// ensure there are enough arguments
	if len(remainingArgs) != function.NArgs()*Word256Length {
		return nil, fmt.Errorf("%s() takes %d arguments", function.Name,
			function.NArgs())
	}

	// call the function
	return function.F(appState, caller, remainingArgs, gas)
}

// We define the address of an SNative contact as the last 20 bytes of the sha3
// hash of its name
func (contract *SNativeContractDescription) Address() abi.Address {
	var address abi.Address
	hash := sha3.Sha3([]byte(contract.Name))
	copy(address[:], hash[len(hash)-abi.AddressLength:])
	return address
}

// Get address as a byte slice
func (contract *SNativeContractDescription) AddressBytes() []byte {
	address := contract.Address()
	return address[:]
}

// Get address as a left-padded Word256
func (contract *SNativeContractDescription) AddressWord256() Word256 {
	return LeftPadWord256(contract.AddressBytes())
}

// Get function by calling identifier FunctionSelector
func (contract *SNativeContractDescription) FunctionByID(id abi.FunctionSelector) (*SNativeFunctionDescription, error) {
	f, ok := contract.functionsByID[id]
	if !ok {
		return nil,
			fmt.Errorf("Unknown SNative function with ID %x", id)
	}
	return f, nil
}

// Get function by name
func (contract *SNativeContractDescription) FunctionByName(name string) (*SNativeFunctionDescription, error) {
	for _, f := range contract.functions {
		if f.Name == name {
			return f, nil
		}
	}
	return nil, fmt.Errorf("Unknown SNative function with name %s", name)
}

// Get functions in order of declaration
func (contract *SNativeContractDescription) Functions() []*SNativeFunctionDescription {
	functions := make([]*SNativeFunctionDescription, len(contract.functions))
	copy(functions, contract.functions)
	return functions
}

//
// SNative functions
//

// Get function signature
func (function *SNativeFunctionDescription) Signature() string {
	argTypeNames := make([]string, len(function.Args))
	for i, arg := range function.Args {
		argTypeNames[i] = string(arg.TypeName)
	}
	return fmt.Sprintf("%s(%s)", function.Name,
		strings.Join(argTypeNames, ","))
}

// Get function calling identifier FunctionSelector
func (function *SNativeFunctionDescription) ID() abi.FunctionSelector {
	return firstFourBytes(sha3.Sha3([]byte(function.Signature())))
}

// Get number of function arguments
func (function *SNativeFunctionDescription) NArgs() int {
	return len(function.Args)
}

func arg(name string, abiTypeName abi.TypeName) abi.Arg {
	return abi.Arg{
		Name:     name,
		TypeName: abiTypeName,
	}
}

func ret(name string, abiTypeName abi.TypeName) abi.Return {
	return abi.Return{
		Name:     name,
		TypeName: abiTypeName,
	}
}

// Permission function defintions

// TODO: catch errors, log em, return 0s to the vm (should some errors cause exceptions though?)
func hasBase(appState AppState, caller *Account, args []byte, gas *int64) (output []byte, err error) {
	addr, permNum := returnTwoArgs(args)
	vmAcc := appState.GetAccount(addr)
	if vmAcc == nil {
		return nil, fmt.Errorf("Unknown account %X", addr)
	}
	permN := ptypes.PermFlag(Uint64FromWord256(permNum)) // already shifted
	if !ValidPermN(permN) {
		return nil, ptypes.ErrInvalidPermission(permN)
	}
	permInt := byteFromBool(HasPermission(appState, vmAcc, permN))
	logger.Debugf("snative.hasBasePerm(0x%X, %b) = %v\n", addr.Postfix(20), permN, permInt)
	return LeftPadWord256([]byte{permInt}).Bytes(), nil
}

func setBase(appState AppState, caller *Account, args []byte, gas *int64) (output []byte, err error) {
	addr, permNum, permVal := returnThreeArgs(args)
	vmAcc := appState.GetAccount(addr)
	if vmAcc == nil {
		return nil, fmt.Errorf("Unknown account %X", addr)
	}
	permN := ptypes.PermFlag(Uint64FromWord256(permNum))
	if !ValidPermN(permN) {
		return nil, ptypes.ErrInvalidPermission(permN)
	}
	permV := !permVal.IsZero()
	if err = vmAcc.Permissions.Base.Set(permN, permV); err != nil {
		return nil, err
	}
	appState.UpdateAccount(vmAcc)
	logger.Debugf("snative.setBasePerm(0x%X, %b, %v)\n", addr.Postfix(20), permN, permV)
	return effectivePermBytes(vmAcc.Permissions.Base, globalPerms(appState)), nil
}

func unsetBase(appState AppState, caller *Account, args []byte, gas *int64) (output []byte, err error) {
	addr, permNum := returnTwoArgs(args)
	vmAcc := appState.GetAccount(addr)
	if vmAcc == nil {
		return nil, fmt.Errorf("Unknown account %X", addr)
	}
	permN := ptypes.PermFlag(Uint64FromWord256(permNum))
	if !ValidPermN(permN) {
		return nil, ptypes.ErrInvalidPermission(permN)
	}
	if err = vmAcc.Permissions.Base.Unset(permN); err != nil {
		return nil, err
	}
	appState.UpdateAccount(vmAcc)
	logger.Debugf("snative.unsetBasePerm(0x%X, %b)\n", addr.Postfix(20), permN)
	return effectivePermBytes(vmAcc.Permissions.Base, globalPerms(appState)), nil
}

func setGlobal(appState AppState, caller *Account, args []byte, gas *int64) (output []byte, err error) {
	permNum, permVal := returnTwoArgs(args)
	vmAcc := appState.GetAccount(ptypes.GlobalPermissionsAddress256)
	if vmAcc == nil {
		sanity.PanicSanity("cant find the global permissions account")
	}
	permN := ptypes.PermFlag(Uint64FromWord256(permNum))
	if !ValidPermN(permN) {
		return nil, ptypes.ErrInvalidPermission(permN)
	}
	permV := !permVal.IsZero()
	if err = vmAcc.Permissions.Base.Set(permN, permV); err != nil {
		return nil, err
	}
	appState.UpdateAccount(vmAcc)
	logger.Debugf("snative.setGlobalPerm(%b, %v)\n", permN, permV)
	return permBytes(vmAcc.Permissions.Base.ResultantPerms()), nil
}

func hasRole(appState AppState, caller *Account, args []byte, gas *int64) (output []byte, err error) {
	addr, role := returnTwoArgs(args)
	vmAcc := appState.GetAccount(addr)
	if vmAcc == nil {
		return nil, fmt.Errorf("Unknown account %X", addr)
	}
	roleS := string(role.Bytes())
	permInt := byteFromBool(vmAcc.Permissions.HasRole(roleS))
	logger.Debugf("snative.hasRole(0x%X, %s) = %v\n", addr.Postfix(20), roleS, permInt > 0)
	return LeftPadWord256([]byte{permInt}).Bytes(), nil
}

func addRole(appState AppState, caller *Account, args []byte, gas *int64) (output []byte, err error) {
	addr, role := returnTwoArgs(args)
	vmAcc := appState.GetAccount(addr)
	if vmAcc == nil {
		return nil, fmt.Errorf("Unknown account %X", addr)
	}
	roleS := string(role.Bytes())
	permInt := byteFromBool(vmAcc.Permissions.AddRole(roleS))
	appState.UpdateAccount(vmAcc)
	logger.Debugf("snative.addRole(0x%X, %s) = %v\n", addr.Postfix(20), roleS, permInt > 0)
	return LeftPadWord256([]byte{permInt}).Bytes(), nil
}

func removeRole(appState AppState, caller *Account, args []byte, gas *int64) (output []byte, err error) {
	addr, role := returnTwoArgs(args)
	vmAcc := appState.GetAccount(addr)
	if vmAcc == nil {
		return nil, fmt.Errorf("Unknown account %X", addr)
	}
	roleS := string(role.Bytes())
	permInt := byteFromBool(vmAcc.Permissions.RmRole(roleS))
	appState.UpdateAccount(vmAcc)
	logger.Debugf("snative.rmRole(0x%X, %s) = %v\n", addr.Postfix(20), roleS, permInt > 0)
	return LeftPadWord256([]byte{permInt}).Bytes(), nil
}

//------------------------------------------------------------------------------------------------
// Errors and utility funcs

type ErrInvalidPermission struct {
	Address Word256
	SNative string
}

func (e ErrInvalidPermission) Error() string {
	return fmt.Sprintf("Account %X does not have permission snative.%s", e.Address.Postfix(20), e.SNative)
}

// Checks if a permission flag is valid (a known base chain or snative permission)
func ValidPermN(n ptypes.PermFlag) bool {
	if n > ptypes.TopPermFlag {
		return false
	}
	return true
}

// Get the global BasePermissions
func globalPerms(appState AppState) ptypes.BasePermissions {
	vmAcc := appState.GetAccount(ptypes.GlobalPermissionsAddress256)
	if vmAcc == nil {
		sanity.PanicSanity("cant find the global permissions account")
	}
	return vmAcc.Permissions.Base
}

// Compute the effective permissions from an Account's BasePermissions by
// taking the bitwise or with the global BasePermissions resultant permissions
func effectivePermBytes(basePerms ptypes.BasePermissions,
	globalPerms ptypes.BasePermissions) []byte {
	return permBytes(basePerms.ResultantPerms() | globalPerms.ResultantPerms())
}

func permBytes(basePerms ptypes.PermFlag) []byte {
	return Uint64ToWord256(uint64(basePerms)).Bytes()
}

// CONTRACT: length has already been checked
func returnTwoArgs(args []byte) (a Word256, b Word256) {
	copy(a[:], args[:32])
	copy(b[:], args[32:64])
	return
}

// CONTRACT: length has already been checked
func returnThreeArgs(args []byte) (a Word256, b Word256, c Word256) {
	copy(a[:], args[:32])
	copy(b[:], args[32:64])
	copy(c[:], args[64:96])
	return
}

func byteFromBool(b bool) byte {
	if b {
		return 0x1
	}
	return 0x0
}

func firstFourBytes(byteSlice []byte) [4]byte {
	var bs [4]byte
	copy(bs[:], byteSlice[:4])
	return bs
}
