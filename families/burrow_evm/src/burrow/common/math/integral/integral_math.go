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

package integral

func MaxInt8(a, b int8) int8 {
	if a > b {
		return a
	}
	return b
}

func MaxUint8(a, b uint8) uint8 {
	if a > b {
		return a
	}
	return b
}

func MaxInt16(a, b int16) int16 {
	if a > b {
		return a
	}
	return b
}

func MaxUint16(a, b uint16) uint16 {
	if a > b {
		return a
	}
	return b
}

func MaxInt32(a, b int32) int32 {
	if a > b {
		return a
	}
	return b
}

func MaxUint32(a, b uint32) uint32 {
	if a > b {
		return a
	}
	return b
}

func MaxInt64(a, b int64) int64 {
	if a > b {
		return a
	}
	return b
}

func MaxUint64(a, b uint64) uint64 {
	if a > b {
		return a
	}
	return b
}

func MaxInt(a, b int) int {
	if a > b {
		return a
	}
	return b
}

func MaxUint(a, b uint) uint {
	if a > b {
		return a
	}
	return b
}

//-----------------------------------------------------------------------------

func MinInt8(a, b int8) int8 {
	if a < b {
		return a
	}
	return b
}

func MinUint8(a, b uint8) uint8 {
	if a < b {
		return a
	}
	return b
}

func MinInt16(a, b int16) int16 {
	if a < b {
		return a
	}
	return b
}

func MinUint16(a, b uint16) uint16 {
	if a < b {
		return a
	}
	return b
}

func MinInt32(a, b int32) int32 {
	if a < b {
		return a
	}
	return b
}

func MinUint32(a, b uint32) uint32 {
	if a < b {
		return a
	}
	return b
}

func MinInt64(a, b int64) int64 {
	if a < b {
		return a
	}
	return b
}

func MinUint64(a, b uint64) uint64 {
	if a < b {
		return a
	}
	return b
}

func MinInt(a, b int) int {
	if a < b {
		return a
	}
	return b
}

func MinUint(a, b uint) uint {
	if a < b {
		return a
	}
	return b
}

//-----------------------------------------------------------------------------

func ExpUint64(a, b uint64) uint64 {
	accum := uint64(1)
	for b > 0 {
		if b&1 == 1 {
			accum *= a
		}
		a *= a
		b >>= 1
	}
	return accum
}
