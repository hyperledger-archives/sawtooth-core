pragma solidity ^0.4.0;

contract HelloWorld {
	function helloWorld() returns(bytes32);
}
contract HelloWorldCaller {
	function callHelloWorld(address helloWorldAddr) returns(bytes32) {
		HelloWorld hello = HelloWorld(helloWorldAddr);
		return hello.helloWorld();
	}
}