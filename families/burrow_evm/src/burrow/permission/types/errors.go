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

package types

import (
	"fmt"
)

//------------------------------------------------------------------------------------------------
// Some errors

// permission number out of bounds
type ErrInvalidPermission PermFlag

func (e ErrInvalidPermission) Error() string {
	return fmt.Sprintf("invalid permission %d", e)
}

// set=false. This error should be caught and the global
// value fetched for the permission by the caller
type ErrValueNotSet PermFlag

func (e ErrValueNotSet) Error() string {
	return fmt.Sprintf("the value for permission %d is not set", e)
}
