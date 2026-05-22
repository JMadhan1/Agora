// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title IUSDC
/// @notice Minimal ERC-20 interface for USDC (6 decimals) on Arc Testnet
/// @dev Arc Testnet USDC: 0x3600000000000000000000000000000000000000
interface IUSDC {
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function approve(address spender, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
    function allowance(address owner, address spender) external view returns (uint256);
    function decimals() external pure returns (uint8);
}
