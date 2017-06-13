/**
 * Copyright 2017 Intel Corporation
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

package handler

import (
	"bytes"
	"crypto/sha512"
	"encoding/hex"
	"fmt"
	"github.com/golang/protobuf/proto"
	"sawtooth_sdk/logging"
	"sawtooth_sdk/processor"
	"sawtooth_sdk/protobuf/processor_pb2"
	"sawtooth_sdk/protobuf/transaction_pb2"
	"strconv"
	"strings"
)

var logger *logging.Logger = logging.Get()
var namespace = hexdigest("xo")[:6]

type XoPayload struct {
	Name   string
	Action string
	Space  int
}

type XoHandler struct {
}

type Game struct {
	Board   string
	State   string
	Player1 string
	Player2 string
	Name    string
}

func (self *XoHandler) FamilyName() string {
	return "xo"
}
func (self *XoHandler) FamilyVersion() string {
	return "1.0"
}
func (self *XoHandler) Encoding() string {
	return "csv-utf8"
}

func (self *XoHandler) Namespaces() []string {
	return []string{namespace}
}

func (self *XoHandler) Apply(request *processor_pb2.TpProcessRequest, state *processor.State) error {
	// The xo player is defined as the signer of the transaction, so we unpack
	// the transaction header to obtain the signer's public key, which will be
	// used as the player's identity.
	header, err := unpackHeader(request.Header)
	if err != nil {
		return err
	}
	player := header.GetSignerPubkey()

	// The payload is sent to the transaction processor as bytes (just as it
	// appears in the transaction constructed by the transactor).  We unpack
	// the payload into an XoPayload struct so we can access its fields.
	payload, err := unpackPayload(request.GetPayload())
	if err != nil {
		return err
	}

	logger.Debugf("xo txn %v: player %v: payload: Name='%v', Action='%v', Space='%v'",
		request.Signature, player, payload.Name, payload.Action, payload.Space)

	switch payload.Action {
	case "create":
		return applyCreate(payload.Name, state)
	case "take":
		return applyTake(payload.Name, payload.Space, player, state)
	default:
		return &processor.InvalidTransactionError{
			fmt.Sprintf("Invalid Action : '%v'", payload.Action)}
	}
}

func applyCreate(name string, state *processor.State) error {
	game, err := loadGame(name, state)
	if err != nil {
		return err
	}
	if game != nil {
		return &processor.InvalidTransactionError{"Game already exists"}
	}

	game = &Game{
		Board:   "---------",
		State:   "P1-NEXT",
		Player1: "",
		Player2: "",
		Name:    name,
	}

	return saveGame(game, state)
}

func applyTake(name string, space int, player string, state *processor.State) error {
	game, err := loadGame(name, state)
	if err != nil {
		return err
	}
	if game == nil {
		return &processor.InvalidTransactionError{"Take requires an existing game"}
	}
	if game.State == "P1-WIN" || game.State == "P2-WIN" || game.State == "TIE" {
		return &processor.InvalidTransactionError{"Game has ended"}
	}

	// Assign players if new game
	if game.Player1 == "" {
		game.Player1 = player
	} else if game.Player2 == "" {
		game.Player2 = player
	}

	if game.Board[space-1] != '-' {
		return &processor.InvalidTransactionError{"Space already taken"}
	}

	if game.State == "P1-NEXT" && player == game.Player1 {
		boardRunes := []rune(game.Board)
		boardRunes[space-1] = 'X'
		game.Board = string(boardRunes)
		game.State = "P2-NEXT"
	} else if game.State == "P2-NEXT" && player == game.Player2 {
		boardRunes := []rune(game.Board)
		boardRunes[space-1] = 'O'
		game.Board = string(boardRunes)
		game.State = "P1-NEXT"
	} else {
		return &processor.InvalidTransactionError{
			fmt.Sprintf("Not this player's turn: '%v'", player)}
	}

	if isWin(game.Board, 'X') {
		game.State = "P1-WIN"
	} else if isWin(game.Board, 'O') {
		game.State = "P2-WIN"
	} else if !strings.Contains(game.Board, "-") {
		game.State = "TIE"
	}

	return saveGame(game, state)
}

func isWin(board string, letter byte) bool {
	wins := [8][3]int{
		{1, 2, 3}, {4, 5, 6}, {7, 8, 9},
		{1, 4, 7}, {2, 5, 8}, {3, 6, 9},
		{1, 5, 9}, {3, 5, 7},
	}

	for _, win := range wins {
		if board[win[0]-1] == letter && board[win[1]-1] == letter && board[win[2]-1] == letter {
			return true
		}
	}
	return false
}

func unpackPayload(payloadData []byte) (*XoPayload, error) {
	if payloadData == nil {
		return nil, &processor.InvalidTransactionError{"Must contain payload"}
	}

	parts := strings.Split(string(payloadData), ",")
	if len(parts) != 3 {
		return nil, &processor.InvalidTransactionError{"Payload is malformed"}
	}

	payload := XoPayload{}
	payload.Name = parts[0]
	payload.Action = parts[1]

	if len(payload.Name) < 1 {
		return nil, &processor.InvalidTransactionError{"Name is required"}
	}

	if len(payload.Action) < 1 {
		return nil, &processor.InvalidTransactionError{"Action is required"}
	}

	if payload.Action == "take" {
		space, err := strconv.Atoi(parts[2])
		if err != nil {
			return nil, &processor.InvalidTransactionError{
				fmt.Sprintf("Invalid Space: '%v'", parts[2])}
		}
		payload.Space = space
	}

	if strings.Contains(payload.Name, "|") {
		return nil, &processor.InvalidTransactionError{
			fmt.Sprintf("Invalid Name (char '|' not allowed): '%v'", parts[2])}
	}

	return &payload, nil
}

func unpackHeader(headerData []byte) (*transaction_pb2.TransactionHeader, error) {
	header := &transaction_pb2.TransactionHeader{}
	err := proto.Unmarshal(headerData, header)
	if err != nil {
		return nil, &processor.InternalError{
			fmt.Sprint("Failed to unmarshal TransactionHeader: %v", err)}
	}
	return header, nil
}

func unpackGame(gameData []byte) (*Game, error) {
	parts := strings.Split(string(gameData), ",")
	if len(parts) != 5 {
		return nil, &processor.InternalError{
			fmt.Sprintf("Malformed game data: '%v'", string(gameData))}
	}

	game := &Game{
		Name:    parts[0],
		Board:   parts[1],
		State:   parts[2],
		Player1: parts[3],
		Player2: parts[4],
	}

	switch game.State {
	case "P1-WIN", "P2-WIN", "TIE", "P1-NEXT", "P2-NEXT":
	default:
		return nil, &processor.InternalError{
			fmt.Sprintf("Game '%v' has reached invalid state: '%v'", string(gameData), game.State)}
	}

	return game, nil
}

func packGame(game *Game) []byte {
	var buffer bytes.Buffer
	buffer.WriteString(game.Name)
	buffer.WriteString(",")
	buffer.WriteString(game.Board)
	buffer.WriteString(",")
	buffer.WriteString(game.State)
	buffer.WriteString(",")
	buffer.WriteString(game.Player1)
	buffer.WriteString(",")
	buffer.WriteString(game.Player2)
	return buffer.Bytes()
}

func loadGame(name string, state *processor.State) (*Game, error) {
	// Use the namespace prefix + the hash of the game name to create the
	// storage address
	address := namespace + hexdigest(name)[:64]

	results, err := state.Get([]string{address})
	if err != nil {
		return nil, &processor.InternalError{fmt.Sprint("Error getting state:", err)}
	}

	if len(string(results[address])) > 0 {
		game, err := unpackGame(results[address])
		if err != nil {
			return nil, err
		}

		// NOTE: Since the game data is stored in a Merkle tree, there is a
		// small chance of collision. A more correct usage would be to store
		// a dictionary of games so that multiple games could be stored at
		// the same location. See the python intkey handler for an example
		// of this.
		if game.Name != name {
			return nil, &processor.InternalError{"Hash collision"}
		}
		return game, nil
	}
	return nil, nil
}

func saveGame(game *Game, state *processor.State) error {
	address := namespace + hexdigest(game.Name)[:64]
	data := packGame(game)

	addresses, err := state.Set(map[string][]byte{
		address: data,
	})
	if err != nil {
		return &processor.InternalError{fmt.Sprint("Failed to set new Value:", err)}
	}
	if len(addresses) == 0 {
		return &processor.InternalError{"No addresses in set response"}
	}
	return nil
}

func hexdigest(str string) string {
	hash := sha512.New()
	hash.Write([]byte(str))
	hashBytes := hash.Sum(nil)
	return strings.ToLower(hex.EncodeToString(hashBytes))
}
