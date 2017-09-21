pragma solidity ^0.4.4;

contract Timestamp {
	function timestamp(bool test) returns (uint) {
		if (test) {
			return block.timestamp;
		} else {
			return 0;
		}
	}
}