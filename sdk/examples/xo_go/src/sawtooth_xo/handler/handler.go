/**
 * Copyright 2017-2018 Intel Corporation
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
	"fmt"
	"sawtooth_sdk/logging"
	"sawtooth_sdk/processor"
	"sawtooth_sdk/protobuf/processor_pb2"
	"sawtooth_xo/xo_payload"
	"sawtooth_xo/xo_state"
	"strings"
)

var logger *logging.Logger = logging.Get()

type XoHandler struct {
}

func (self *XoHandler) FamilyName() string {
	return "xo"
}

func (self *XoHandler) FamilyVersions() []string {
	return []string{"1.0"}
}

func (self *XoHandler) Namespaces() []string {
	return []string{xo_state.Namespace}
}

func (self *XoHandler) Apply(request *processor_pb2.TpProcessRequest, context *processor.Context) error {
	// The xo player is defined as the signer of the transaction, so we unpack
	// the transaction header to obtain the signer's public key, which will be
	// used as the player's identity.
	header := request.GetHeader()
	player := header.GetSignerPublicKey()

	// The payload is sent to the transaction processor as bytes (just as it
	// appears in the transaction constructed by the transactor).  We unpack
	// the payload into an XoPayload struct so we can access its fields.
	payload, err := xo_payload.FromBytes(request.GetPayload())
	if err != nil {
		return err
	}

	xoState := xo_state.NewXoState(context)

	logger.Debugf("xo txn %v: player %v: payload: Name='%v', Action='%v', Space='%v'",
		request.Signature, player, payload.Name, payload.Action, payload.Space)

	switch payload.Action {
	case "create":
		err := validateCreate(xoState, payload.Name)
		if err != nil {
			return err
		}
		game := &xo_state.Game{
			Board:   "---------",
			State:   "P1-NEXT",
			Player1: "",
			Player2: "",
			Name:    payload.Name,
		}
		displayCreate(payload, player)
		return xoState.SetGame(payload.Name, game)
	case "delete":
		err := validateDelete(xoState, payload.Name)
		if err != nil {
			return err
		}
		return xoState.DeleteGame(payload.Name)
	case "take":
		err := validateTake(xoState, payload, player)
		if err != nil {
			return err
		}
		game, err := xoState.GetGame(payload.Name)
		if err != nil {
			return err
		}
		// Assign players if new game
		if game.Player1 == "" {
			game.Player1 = player
		} else if game.Player2 == "" {
			game.Player2 = player
		}

		if game.State == "P1-NEXT" && player == game.Player1 {
			boardRunes := []rune(game.Board)
			boardRunes[payload.Space-1] = 'X'
			game.Board = string(boardRunes)
			game.State = "P2-NEXT"
		} else if game.State == "P2-NEXT" && player == game.Player2 {
			boardRunes := []rune(game.Board)
			boardRunes[payload.Space-1] = 'O'
			game.Board = string(boardRunes)
			game.State = "P1-NEXT"
		} else {
			return &processor.InvalidTransactionError{
				Msg: fmt.Sprintf("Not this player's turn: '%v'", player)}
		}

		if isWin(game.Board, 'X') {
			game.State = "P1-WIN"
		} else if isWin(game.Board, 'O') {
			game.State = "P2-WIN"
		} else if !strings.Contains(game.Board, "-") {
			game.State = "TIE"
		}
		displayTake(payload, player, game)
		return xoState.SetGame(payload.Name, game)
	default:
		return &processor.InvalidTransactionError{
			Msg: fmt.Sprintf("Invalid Action : '%v'", payload.Action)}
	}
}

func validateCreate(xoState *xo_state.XoState, name string) error {
	game, err := xoState.GetGame(name)
	if err != nil {
		return err
	}
	if game != nil {
		return &processor.InvalidTransactionError{Msg: "Game already exists"}
	}

	return nil
}

func validateDelete(xoState *xo_state.XoState, name string) error {
	game, err := xoState.GetGame(name)
	if err != nil {
		return err
	}
	if game == nil {
		return &processor.InvalidTransactionError{Msg: "Delete requires an existing game"}
	}
	return nil
}

func validateTake(xoState *xo_state.XoState, payload *xo_payload.XoPayload, signer string) error {
	game, err := xoState.GetGame(payload.Name)
	if err != nil {
		return err
	}
	if game == nil {
		return &processor.InvalidTransactionError{Msg: "Take requires an existing game"}
	}
	if game.State == "P1-WIN" || game.State == "P2-WIN" || game.State == "TIE" {
		return &processor.InvalidTransactionError{Msg: "Game has ended"}
	}

	if game.State == "P1-WIN" || game.State == "P2-WIN" || game.State == "TIE" {
		return &processor.InvalidTransactionError{
			Msg: "Invalid Action: Game has ended"}
	}

	if game.Board[payload.Space-1] != '-' {
		return &processor.InvalidTransactionError{Msg: "Space already taken"}
	}
	return nil
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

func displayCreate(payload *xo_payload.XoPayload, signer string) {
	s := fmt.Sprintf("+ Player %s created game %s +", signer[:6], payload.Name)
	sLength := len(s)
	border := "+" + strings.Repeat("-", sLength-2) + "+"
	fmt.Println(border)
	fmt.Println(s)
	fmt.Println(border)
}

func displayTake(payload *xo_payload.XoPayload, signer string, game *xo_state.Game) {
	s := fmt.Sprintf("+ Player %s takes space %d +", signer[:6], payload.Space)
	sLength := len(s)
	border := "+" + strings.Repeat("-", sLength-2) + "+"
	blank := "+" + strings.Repeat(" ", sLength-2) + "+"
	g := center(fmt.Sprintf("%s: %s", "Game", game.Name), sLength)
	state := center(fmt.Sprintf("%s: %s", "State", game.State), sLength)
	p1 := center(fmt.Sprintf("%s: %s", "Player1", sliceIfLongEnough(game.Player1, 6)), sLength)
	p2 := center(fmt.Sprintf("%s: %s", "Player2", sliceIfLongEnough(game.Player2, 6)), sLength)
	space := strings.Repeat(" ", (sLength-2-11)/2)
	xoBoardLine := "+" + space + "---|---|---" + space + "+"
	xoBoardSpace := "+" + space + " %c | %c | %c " + space + "+\n"
	fmt.Println(border)
	fmt.Println(s)
	fmt.Println(blank)
	fmt.Println(g)
	fmt.Println(state)
	fmt.Println(p1)
	fmt.Println(p2)
	fmt.Printf(xoBoardSpace, blankify(game.Board[0]), blankify(game.Board[1]), blankify(game.Board[2]))
	fmt.Println(xoBoardLine)
	fmt.Printf(xoBoardSpace, blankify(game.Board[3]), blankify(game.Board[4]), blankify(game.Board[5]))
	fmt.Println(xoBoardLine)
	fmt.Printf(xoBoardSpace, blankify(game.Board[6]), blankify(game.Board[7]), blankify(game.Board[8]))
	fmt.Println(border)
}

func blankify(char byte) byte {
	if char == '-' {
		return ' '
	}
	return char
}

func center(text string, width int) string {
	l := len(text)
	space := width - l - 2
	if space%2 == 0 {
		s1 := strings.Repeat(" ", space/2)
		s2 := strings.Repeat(" ", space/2)
		return "+" + s1 + text + s2 + "+"
	}
	s1 := strings.Repeat(" ", space/2)
	s2 := strings.Repeat(" ", space/2+1)
	return "+" + s1 + text + s2 + "+"
}

func sliceIfLongEnough(text string, num int) string {
	if len(text) > num {
		return text[:num]
	} else if len(text) > 0 {
		return text[:len(text)-1]
	}
	return text
}
