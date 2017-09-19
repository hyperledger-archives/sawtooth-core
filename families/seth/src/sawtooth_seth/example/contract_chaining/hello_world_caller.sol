pragma solidity ^0.4.0;

contract HelloWorld {
	function helloWorld() returns(bytes32);
}
contract HelloWorldCaller {
	bytes32 public data = "";

	function callHelloWorld(address helloWorldAddr) {
		HelloWorld hello = HelloWorld(helloWorldAddr);
		data = hello.helloWorld();
	}
}