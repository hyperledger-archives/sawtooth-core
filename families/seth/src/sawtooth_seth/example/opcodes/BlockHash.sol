pragma solidity ^0.4.4;

contract BlockHash {
	function blockHash(uint64 blockNum) returns (bytes32) {
		return block.blockhash(blockNum);
	}
}