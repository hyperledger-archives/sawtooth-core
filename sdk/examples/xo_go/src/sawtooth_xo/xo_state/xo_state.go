/**
 * Copyright 2018 Intel Corporation
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

package xo_state

import (
	"bytes"
	"crypto/sha512"
	"encoding/hex"
	"fmt"
	"sawtooth_sdk/processor"
	"sort"
	"strings"
)

var Namespace = hexdigest("xo")[:6]

type Game struct {
	Board   string
	State   string
	Player1 string
	Player2 string
	Name    string
}

// XoState handles addressing, serialization, deserialization,
// and holding an addressCache of data at the address.
type XoState struct {
	context      *processor.Context
	addressCache map[string][]byte
}

// NewXoState constructs a new XoState struct.
func NewXoState(context *processor.Context) *XoState {
	return &XoState{
		context:      context,
		addressCache: make(map[string][]byte),
	}
}

// GetGame returns a game by it's name.
func (self *XoState) GetGame(name string) (*Game, error) {
	games, err := self.loadGames(name)
	if err != nil {
		return nil, err
	}
	game, ok := games[name]
	if ok {
		return game, nil
	}
	return nil, nil
}

// SetGame sets a game to it's name
func (self *XoState) SetGame(name string, game *Game) error {
	games, err := self.loadGames(name)
	if err != nil {
		return err
	}

	games[name] = game

	return self.storeGames(name, games)
}

// DeleteGame deletes the game from state, handling
// hash collisions.
func (self *XoState) DeleteGame(name string) error {
	games, err := self.loadGames(name)
	if err != nil {
		return err
	}
	delete(games, name)
	if len(games) > 0 {
		return self.storeGames(name, games)
	} else {
		return self.deleteGames(name)
	}
}

func (self *XoState) loadGames(name string) (map[string]*Game, error) {
	address := makeAddress(name)

	data, ok := self.addressCache[address]
	if ok {
		if self.addressCache[address] != nil {
			return deserialize(data)
		}
		return make(map[string]*Game), nil

	}
	results, err := self.context.GetState([]string{address})
	if err != nil {
		return nil, err
	}
	if len(string(results[address])) > 0 {
		self.addressCache[address] = results[address]
		return deserialize(results[address])
	}
	self.addressCache[address] = nil
	games := make(map[string]*Game)
	return games, nil
}

func (self *XoState) storeGames(name string, games map[string]*Game) error {
	address := makeAddress(name)

	var names []string
	for name := range games {
		names = append(names, name)
	}
	sort.Strings(names)

	var g []*Game
	for _, name := range names {
		g = append(g, games[name])
	}

	data := serialize(g)

	self.addressCache[address] = data

	_, err := self.context.SetState(map[string][]byte{
		address: data,
	})
	return err
}

func (self *XoState) deleteGames(name string) error {
	address := makeAddress(name)

	_, err := self.context.DeleteState([]string{address})
	return err
}

func deserialize(data []byte) (map[string]*Game, error) {
	games := make(map[string]*Game)
	for _, str := range strings.Split(string(data), "|") {

		parts := strings.Split(string(str), ",")
		if len(parts) != 5 {
			return nil, &processor.InternalError{
				Msg: fmt.Sprintf("Malformed game data: '%v'", string(data))}
		}

		game := &Game{
			Name:    parts[0],
			Board:   parts[1],
			State:   parts[2],
			Player1: parts[3],
			Player2: parts[4],
		}
		games[parts[0]] = game
	}

	return games, nil
}

func serialize(games []*Game) []byte {
	var buffer bytes.Buffer
	for i, game := range games {

		buffer.WriteString(game.Name)
		buffer.WriteString(",")
		buffer.WriteString(game.Board)
		buffer.WriteString(",")
		buffer.WriteString(game.State)
		buffer.WriteString(",")
		buffer.WriteString(game.Player1)
		buffer.WriteString(",")
		buffer.WriteString(game.Player2)
		if i+1 != len(games) {
			buffer.WriteString("|")
		}
	}
	return buffer.Bytes()
}

func makeAddress(name string) string {
	return Namespace + hexdigest(name)[:64]
}

func hexdigest(str string) string {
	hash := sha512.New()
	hash.Write([]byte(str))
	hashBytes := hash.Sum(nil)
	return strings.ToLower(hex.EncodeToString(hashBytes))
}
