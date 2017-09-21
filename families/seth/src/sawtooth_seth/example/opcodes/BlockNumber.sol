pragma solidity ^0.4.4;

contract BlockNumber {
	function blockNumber(uint number) returns (uint) {
		return block.number - number;
	}
}