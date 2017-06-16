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

package word256

// NOTE: [ben] this used to be in tendermint/go-common but should be
// isolated and cleaned up and tested.  Should be used in permissions
// and manager/burrow-mint
// TODO: [ben] cleanup, but also write unit-tests

import (
	"encoding/binary"
	"sort"
)

// Sort for []uint64

type Uint64Slice []uint64

func (p Uint64Slice) Len() int           { return len(p) }
func (p Uint64Slice) Less(i, j int) bool { return p[i] < p[j] }
func (p Uint64Slice) Swap(i, j int)      { p[i], p[j] = p[j], p[i] }
func (p Uint64Slice) Sort()              { sort.Sort(p) }

func SearchUint64s(a []uint64, x uint64) int {
	return sort.Search(len(a), func(i int) bool { return a[i] >= x })
}

func (p Uint64Slice) Search(x uint64) int { return SearchUint64s(p, x) }

//--------------------------------------------------------------------------------

func PutUint64LE(dest []byte, i uint64) {
	binary.LittleEndian.PutUint64(dest, i)
}

func GetUint64LE(src []byte) uint64 {
	return binary.LittleEndian.Uint64(src)
}

func PutUint64BE(dest []byte, i uint64) {
	binary.BigEndian.PutUint64(dest, i)
}

func GetUint64BE(src []byte) uint64 {
	return binary.BigEndian.Uint64(src)
}

func PutInt64LE(dest []byte, i int64) {
	binary.LittleEndian.PutUint64(dest, uint64(i))
}

func GetInt64LE(src []byte) int64 {
	return int64(binary.LittleEndian.Uint64(src))
}

func PutInt64BE(dest []byte, i int64) {
	binary.BigEndian.PutUint64(dest, uint64(i))
}

func GetInt64BE(src []byte) int64 {
	return int64(binary.BigEndian.Uint64(src))
}
