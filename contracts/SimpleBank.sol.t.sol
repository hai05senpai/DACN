// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract SimpleBank {
    mapping(address => uint256) public balances;

    function deposit() public payable {
        balances[msg.sender] += msg.value;
    }

    // Lỗi Reentrancy: Chuyển tiền trước khi hạ balance xuống 0
    function withdraw() public {
        uint256 balance = balances[msg.sender];
        require(balance > 0, "So du khong du");
        
        (bool success, ) = msg.sender.call{value: balance}("");
        require(success, unicode"Rut tien thất bai");

        balances[msg.sender] = 0; 
    }
}
