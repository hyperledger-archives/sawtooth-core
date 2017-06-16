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

package sanity

import (
	"fmt"
)

//--------------------------------------------------------------------------------------------------
// panic wrappers
// NOTE: [ben] Fail fast and fail hard, these are wrappers that point to code that needs
// to be addressed, but simplify finding them in the code;

// A panic resulting from a sanity check means there is a programmer error
// and some gaurantee is not satisfied.
func PanicSanity(v interface{}) {
	panic(fmt.Sprintf("Paniced on a Sanity Check: %v", v))
}

// A panic here means something has gone horribly wrong, in the form of data corruption or
// failure of the operating system. In a correct/healthy system, these should never fire.
// If they do, it's indicative of a much more serious problem.
func PanicCrisis(v interface{}) {
	panic(fmt.Sprintf("Paniced on a Crisis: %v", v))
}

// Indicates a failure of consensus. Someone was malicious or something has
// gone horribly wrong. These should really boot us into an "emergency-recover" mode
func PanicConsensus(v interface{}) {
	panic(fmt.Sprintf("Paniced on a Consensus Failure: %v", v))
}

// For those times when we're not sure if we should panic
func PanicQ(v interface{}) {
	panic(fmt.Sprintf("Paniced questionably: %v", v))
}
