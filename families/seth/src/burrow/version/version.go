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

package version

// version provides the current burrow version and a VersionIdentifier
// for the modules to identify their version with.

import (
	"fmt"
)

// IMPORTANT: this version number needs to be manually kept
// in sync at the bottom of this file for the deployment scripts to parse
// the version number.
const (
	// Client identifier to advertise over the network
	clientIdentifier = "burrow"
	// Major version component of the current release
	versionMajor = 0
	// Minor version component of the current release
	versionMinor = 17
	// Patch version component of the current release
	versionPatch = 0
)

var version *VersionIdentifier

func init() {
	version = New(clientIdentifier, versionMajor, versionMinor, versionPatch)
}

//------------------------------------------------------------------------------
// versioning globally for burrow and scoped for modules

type VersionIdentifier struct {
	clientIdentifier string
	versionMajor     uint8
	versionMinor     uint8
	versionPatch     uint8
}

func New(client string, major, minor, patch uint8) *VersionIdentifier {
	v := new(VersionIdentifier)
	v.clientIdentifier = client
	v.versionMajor = major
	v.versionMinor = minor
	v.versionPatch = patch
	return v
}

// GetVersionString returns `client-major.minor.patch` for burrow
// without a receiver, or for the version called on.
// MakeVersionString builds the same version string with provided parameters.
func GetVersionString() string { return version.GetVersionString() }
func (v *VersionIdentifier) GetVersionString() string {
	return fmt.Sprintf("%s-%d.%d.%d", v.clientIdentifier, v.versionMajor,
		v.versionMinor, v.versionPatch)
}

// note: the arguments are passed in as int (rather than uint8)
// because on asserting the version constructed from the configuration file
// the casting of an int to uint8 is uglier than expanding the type range here.
// Should the configuration file have an invalid integer (that could not convert)
// then this will equally be reflected in a failed assertion of the version string.
func MakeVersionString(client string, major, minor, patch int) string {
	return fmt.Sprintf("%s-%d.%d.%d", client, major, minor, patch)
}

// GetMinorVersionString returns `client-major.minor` for burrow
// without a receiver, or for the version called on.
// MakeMinorVersionString builds the same version string with
// provided parameters.
func GetMinorVersionString() string { return version.GetVersionString() }
func (v *VersionIdentifier) GetMinorVersionString() string {
	return fmt.Sprintf("%s-%d.%d", v.clientIdentifier, v.versionMajor,
		v.versionMinor)
}

// note: similar remark applies here on the use of `int` over `uint8`
// for the arguments as above for MakeVersionString()
func MakeMinorVersionString(client string, major, minor, patch int) string {
	return fmt.Sprintf("%s-%d.%d", client, major, minor)
}

// GetVersion returns a tuple of client, major, minor, and patch as types,
// either for burrow without a receiver or the called version structure.
func GetVersion() (client string, major, minor, patch uint8) {
	return version.GetVersion()
}
func (version *VersionIdentifier) GetVersion() (
	client string, major, minor, patch uint8) {
	return version.clientIdentifier, version.versionMajor, version.versionMinor,
		version.versionPatch
}

//------------------------------------------------------------------------------
// Matching functions

// MatchesMinorVersion matches the client identifier, major and minor version
// number of the reference version identifier to be equal with the receivers.
func MatchesMinorVersion(referenceVersion *VersionIdentifier) bool {
	return version.MatchesMinorVersion(referenceVersion)
}
func (version *VersionIdentifier) MatchesMinorVersion(
	referenceVersion *VersionIdentifier) bool {
	referenceClient, referenceMajor, referenceMinor, _ := referenceVersion.GetVersion()
	return version.clientIdentifier == referenceClient &&
		version.versionMajor == referenceMajor &&
		version.versionMinor == referenceMinor
}

//------------------------------------------------------------------------------
// Version number for tests/build_tool.sh

// IMPORTANT: burrow version must be on the last line of this file for
// the deployment script tests/build_tool.sh to pick up the right label.
const VERSION = "0.17.0"
