/* Copyright 2017 Intel Corporation
 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

     http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
------------------------------------------------------------------------------*/

package sawtooth.examples.xo;


import com.google.protobuf.ByteString;
import com.google.protobuf.InvalidProtocolBufferException;

import org.apache.commons.lang3.StringUtils;

import sawtooth.sdk.processor.State;
import sawtooth.sdk.processor.TransactionHandler;
import sawtooth.sdk.processor.Utils;
import sawtooth.sdk.processor.exceptions.InternalError;
import sawtooth.sdk.processor.exceptions.InvalidTransactionException;
import sawtooth.sdk.protobuf.TpProcessRequest;
import sawtooth.sdk.protobuf.TransactionHeader;

import java.io.UnsupportedEncodingException;
import java.util.AbstractMap;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collection;
import java.util.Collections;
import java.util.Map;
import java.util.logging.Logger;

public class XoHandler implements TransactionHandler {

  private final Logger logger = Logger.getLogger(XoHandler.class.getName());
  private String xoNameSpace;

  /**
   * constructor.
   */
  public XoHandler() {
    try {
      this.xoNameSpace = Utils.hash512(
        this.transactionFamilyName().getBytes("UTF-8")).substring(0, 6);
    } catch (UnsupportedEncodingException usee) {
      usee.printStackTrace();
      this.xoNameSpace = "";
    }
  }

  @Override
  public String transactionFamilyName() {
    return "xo";
  }

  @Override
  public String getVersion() {
    return "1.0";
  }

  @Override
  public Collection<String> getNameSpaces() {
    ArrayList<String> namespaces = new ArrayList<>();
    namespaces.add(this.xoNameSpace);
    return namespaces;
  }

  class TransactionData {
    final String gameName;
    final String action;
    final String space;

    TransactionData(String gameName, String action, String space) {
      this.gameName = gameName;
      this.action = action;
      this.space = space;
    }
  }

  class GameData {
    final String gameName;
    final String board;
    final String state;
    final String playerOne;
    final String playerTwo;

    GameData(String gameName, String board, String state, String playerOne, String playerTwo) {
      this.gameName = gameName;
      this.board = board;
      this.state = state;
      this.playerOne = playerOne;
      this.playerTwo = playerTwo;
    }
  }

  @Override
  public void apply(TpProcessRequest transactionRequest, State stateStore)
      throws InvalidTransactionException, InternalError {
    TransactionData transactionData = getUnpackedTransaction(transactionRequest);

    // The transaction signer is the player
    String player;
    TransactionHeader header = transactionRequest.getHeader();
    player = header.getSignerPublicKey();

    if (transactionData.gameName.equals("")) {
      throw new InvalidTransactionException("Name is required");
    }
    if (transactionData.gameName.contains("|")) {
      throw new InvalidTransactionException("Game name cannot contain '|'");
    }
    if (transactionData.action.equals("")) {
      throw new InvalidTransactionException("Action is required");
    }
    if (transactionData.action.equals("take")) {
      try {
        int space = Integer.parseInt(transactionData.space);

        if (space < 1 || space > 9) {
          throw new InvalidTransactionException(
              String.format("Invalid space: %s", transactionData.space));
        }
      } catch (NumberFormatException e) {
        throw new InvalidTransactionException("Space could not be converted to an integer.");
      }
    }
    if (!transactionData.action.equals("take") && !transactionData.action.equals("create")) {
      throw new InvalidTransactionException(
          String.format("Invalid action: %s", transactionData.action));
    }

    String address = makeGameAddress(transactionData.gameName);
    // stateStore.get() returns a list.
    // If no data has been stored yet at the given address, it will be empty.
    String stateEntry = stateStore.getState(
        Collections.singletonList(address)
    ).get(address).toStringUtf8();
    GameData stateData = getStateData(stateEntry, transactionData.gameName);
    GameData updatedGameData = playXo(transactionData, stateData, player);
    storeGameData(address, updatedGameData, stateEntry, stateStore);
  }

  /**
   * Helper function to retrieve game gameName, action, and space from transaction request.
   */
  private TransactionData getUnpackedTransaction(TpProcessRequest transactionRequest)
      throws InvalidTransactionException {
    String payload =  transactionRequest.getPayload().toStringUtf8();
    ArrayList<String> payloadList = new ArrayList<>(Arrays.asList(payload.split(",")));
    if (payloadList.size() > 3) {
      throw new InvalidTransactionException("Invalid payload serialization");
    }
    while (payloadList.size() < 3) {
      payloadList.add("");
    }
    return new TransactionData(payloadList.get(0), payloadList.get(1), payloadList.get(2));
  }

  /**
   * Helper function to retrieve the board, state, playerOne, and playerTwo from state store.
   */
  private GameData getStateData(String stateEntry, String gameName)
      throws InternalError, InvalidTransactionException {
    if (stateEntry.length() == 0) {
      return new GameData("", "", "", "", "");
    } else {
      try {
        String gameCsv = getGameCsv(stateEntry, gameName);
        ArrayList<String> gameList = new ArrayList<>(Arrays.asList(gameCsv.split(",")));
        while (gameList.size() < 5) {
          gameList.add("");
        }
        return new GameData(gameList.get(0), gameList.get(1),
            gameList.get(2), gameList.get(3), gameList.get(4));
      } catch (Error e) {
        throw new InternalError("Failed to deserialize game data");
      }
    }
  }

  /**
   * Helper function to generate game address.
   */
  private String makeGameAddress(String gameName) throws InternalError {
    try {
      String hashedName = Utils.hash512(gameName.getBytes("UTF-8"));
      return xoNameSpace + hashedName.substring(0, 64);
    } catch (UnsupportedEncodingException e) {
      throw new InternalError("Internal Error: " + e.toString());
    }
  }

  /**
   * Helper function to retrieve the correct game info from the list of game data CSV.
   */
  private String getGameCsv(String stateEntry, String gameName) {
    ArrayList<String> gameCsvList = new ArrayList<>(Arrays.asList(stateEntry.split("\\|")));
    for (String gameCsv : gameCsvList) {
      if (gameCsv.regionMatches(0, gameName, 0, gameName.length())) {
        return gameCsv;
      }
    }
    return "";
  }

  /**
   * Helper function to store state data.
   */
  private void storeGameData(String address, GameData gameData, String stateEntry, State stateStore)
      throws InternalError, InvalidTransactionException {
    String gameDataCsv = String.format("%s,%s,%s,%s,%s",
        gameData.gameName, gameData.board, gameData.state, gameData.playerOne, gameData.playerTwo);
    if (stateEntry.length() == 0) {
      stateEntry = gameDataCsv;
    } else {
      ArrayList<String> dataList = new ArrayList<>(Arrays.asList(stateEntry.split("\\|")));
      for (int i = 0; i <= dataList.size(); i++) {
        if (i == dataList.size()
            || dataList.get(i).regionMatches(0, gameData.gameName, 0, gameData.gameName.length())) {
          dataList.set(i, gameDataCsv);
          break;
        }
      }
      stateEntry = StringUtils.join(dataList, "|");
    }

    ByteString csvByteString = ByteString.copyFromUtf8(stateEntry);
    Map.Entry<String, ByteString> entry = new AbstractMap.SimpleEntry<>(address, csvByteString);
    Collection<Map.Entry<String, ByteString>> addressValues = Collections.singletonList(entry);
    Collection<String> addresses = stateStore.setState(addressValues);
    if (addresses.size() < 1) {
      throw new InternalError("State Error");
    }
  }

  /**
   * Function that handles game logic.
   */
  private GameData playXo(TransactionData transactionData, GameData gameData, String player)
      throws InvalidTransactionException, InternalError {
    switch (transactionData.action) {
      case "create":
        return applyCreate(transactionData, gameData, player);
      case "take":
        return applyTake(transactionData, gameData, player);
      default:
        throw new InvalidTransactionException(String.format(
            "Invalid action: %s", transactionData.action));
    }
  }

  /**
   * Function that handles game logic for 'create' action.
   */
  private GameData applyCreate(TransactionData transactionData, GameData gameData, String player)
      throws InvalidTransactionException {
    if (!gameData.board.equals("")) {
      throw new InvalidTransactionException("Invalid Action: Game already exists");
    }
    display(String.format("Player %s created a game", abbreviate(player)));
    return new GameData(transactionData.gameName, "---------", "P1-NEXT", "", "");
  }

  /**
   * Function that handles game logic for 'take' action.
   */
  private GameData applyTake(TransactionData transactionData, GameData gameData, String player)
      throws InvalidTransactionException, InternalError {
    if (Arrays.asList("P1-WIN", "P2-WIN", "TIE").contains(gameData.state)) {
      throw new InvalidTransactionException("Invalid action: Game has ended");
    }
    if (gameData.board.equals("")) {
      throw new InvalidTransactionException("Invalid action: 'take' requires an existing game");
    }
    if (!Arrays.asList("P1-NEXT", "P2-NEXT").contains(gameData.state)) {
      throw new InternalError(String.format(
          "Internal Error: Game has reached an invalid state: %s", gameData.state));
    }

    // Assign players if new game
    String updatedPlayerOne = gameData.playerOne;
    String updatedPlayerTwo = gameData.playerTwo;
    if (gameData.playerOne.equals("")) {
      updatedPlayerOne = player;
    } else if (gameData.playerTwo.equals("")) {
      updatedPlayerTwo = player;
    }

    // Verify player identity and take space
    int space = Integer.parseInt(transactionData.space);
    char[] boardList = gameData.board.toCharArray();
    String updatedState;
    if (boardList[space - 1] != '-') {
      throw new InvalidTransactionException("Space already taken");
    }

    if (gameData.state.equals("P1-NEXT") && player.equals(updatedPlayerOne)) {
      boardList[space - 1] = 'X';
      updatedState = "P2-NEXT";
    } else if (gameData.state.equals("P2-NEXT") && player.equals(updatedPlayerTwo)) {
      boardList[space - 1] = 'O';
      updatedState = "P1-NEXT";
    } else {
      throw new InvalidTransactionException(String.format(
          "Not this player's turn: %s", abbreviate(player)));
    }

    String updatedBoard = String.valueOf(boardList);
    updatedState = determineState(boardList, updatedState);
    GameData updatedGameData = new GameData(
        gameData.gameName, updatedBoard, updatedState, updatedPlayerOne, updatedPlayerTwo);

    display(
        String.format("Player %s takes space %d \n", abbreviate(player), space)
            + gameDataToString(updatedGameData));
    return updatedGameData;
  }

  /**
   * Helper function that updates game state based on the current board position.
   */
  private String determineState(char[] boardList, String state) {
    if (isWin(boardList, 'X')) {
      state = "P1-WIN";
    } else if (isWin(boardList, 'O')) {
      state = "P2-WIN";
    } else if (!(String.valueOf(boardList).contains("-"))) {
      state = "TIE";
    }
    return state;
  }

  /**
   * Helper function that analyzes board position to determine if it is in a winning state.
   */
  private boolean isWin(char[] board, char letter) {
    int[][] wins = new int[][]{
        {1, 2, 3}, {4, 5, 6}, {7, 8, 9},
        {1, 4, 7}, {2, 5, 8}, {3, 6, 9},
        {1, 5, 9}, {3, 5, 7},
    };

    for (int[] win : wins) {
      if (board[win[0] - 1] == letter
          && board[win[1] - 1] == letter
          && board[win[2] - 1] == letter) {
        return true;
      }
    }
    return false;
  }

  /**
   * Helper function to create an ASCII representation of the board.
   */
  private String gameDataToString(GameData gameData) {
    String out = "";
    out += String.format("GAME: %s\n", gameData.gameName);
    out += String.format("PLAYER 1: %s\n", abbreviate(gameData.playerOne));
    out += String.format("PLAYER 2: %s\n", abbreviate(gameData.playerTwo));
    out += String.format("STATE: %s\n", gameData.state);
    out += "\n";

    char[] board = gameData.board.replace('-',' ').toCharArray();
    out += String.format("%c | %c |  %c\n", board[0], board[1], board[2]);
    out += "---|---|---\n";
    out += String.format("%c | %c |  %c\n", board[3], board[4], board[5]);
    out += "---|---|---\n";
    out += String.format("%c | %c |  %c\n", board[6], board[7], board[8]);
    return out;
  }

  /**
   * Helper function to print game data to the logger.
   */
  private void display(String msg) {
    String displayMsg = "";
    int length = 0;
    String[] msgLines = msg.split("\n");
    if (msg.contains("\n")) {
      for (String line : msgLines) {
        if (line.length() > length) {
          length = line.length();
        }
      }
    } else {
      length = msg.length();
    }

    displayMsg = displayMsg.concat("\n+" + printDashes(length + 2) + "+\n");
    for (String line : msgLines) {
      displayMsg = displayMsg.concat("+" + StringUtils.center(line, length + 2) + "+\n");
    }
    displayMsg = displayMsg.concat("+" + printDashes(length + 2) + "+");
    logger.info(displayMsg);
  }

  /**
   * Helper function to create a string with a specified number of dashes (for logging purposes).
   */
  private String printDashes(int length) {
    String dashes = "";
    for (int i = 0; i < length; i++) {
      dashes = dashes.concat("-");
    }
    return dashes;
  }

  /**
   * Helper function to shorten a string to a max of 6 characters for logging purposes.
   */
  private Object abbreviate(String player) {
    return player.substring(0, Math.min(player.length(), 6));
  }
}
