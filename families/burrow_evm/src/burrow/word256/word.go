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
	"bytes"
	"sort"
)

var (
	Zero256 = Word256{0}
	One256  = Word256{1}
)

const Word256Length = 32

type Word256 [Word256Length]byte

func (w Word256) String() string        { return string(w[:]) }
func (w Word256) TrimmedString() string { return TrimmedString(w.Bytes()) }
func (w Word256) Copy() Word256         { return w }
func (w Word256) Bytes() []byte         { return w[:] } // copied.
func (w Word256) Prefix(n int) []byte   { return w[:n] }
func (w Word256) Postfix(n int) []byte  { return w[32-n:] }
func (w Word256) IsZero() bool {
	accum := byte(0)
	for _, byt := range w {
		accum |= byt
	}
	return accum == 0
}
func (w Word256) Compare(other Word256) int {
	return bytes.Compare(w[:], other[:])
}

func Uint64ToWord256(i uint64) Word256 {
	buf := [8]byte{}
	PutUint64BE(buf[:], i)
	return LeftPadWord256(buf[:])
}

func Int64ToWord256(i int64) Word256 {
	buf := [8]byte{}
	PutInt64BE(buf[:], i)
	return LeftPadWord256(buf[:])
}

func RightPadWord256(bz []byte) (word Word256) {
	copy(word[:], bz)
	return
}

func LeftPadWord256(bz []byte) (word Word256) {
	copy(word[32-len(bz):], bz)
	return
}

func Uint64FromWord256(word Word256) uint64 {
	buf := word.Postfix(8)
	return GetUint64BE(buf)
}

func Int64FromWord256(word Word256) int64 {
	buf := word.Postfix(8)
	return GetInt64BE(buf)
}

//-------------------------------------

type Tuple256 struct {
	First  Word256
	Second Word256
}

func (tuple Tuple256) Compare(other Tuple256) int {
	firstCompare := tuple.First.Compare(other.First)
	if firstCompare == 0 {
		return tuple.Second.Compare(other.Second)
	} else {
		return firstCompare
	}
}

func Tuple256Split(t Tuple256) (Word256, Word256) {
	return t.First, t.Second
}

type Tuple256Slice []Tuple256

func (p Tuple256Slice) Len() int { return len(p) }
func (p Tuple256Slice) Less(i, j int) bool {
	return p[i].Compare(p[j]) < 0
}
func (p Tuple256Slice) Swap(i, j int) { p[i], p[j] = p[j], p[i] }
func (p Tuple256Slice) Sort()         { sort.Sort(p) }
