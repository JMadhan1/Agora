// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title IUSYC
/// @notice Interface for USYC tokenized money market fund on Arc Testnet
/// @dev USYC Teller: 0x9fdF14c5B14173D74C08Af27AebFf39240dC105A
/// @dev USYC Token: 0xe9185F0c5F296Ed1797AaE4238D26CCaBEadb86C
interface IUSYCTeller {
    /// @notice Deposit USDC to receive USYC shares
    /// @param usdcAmount Amount of USDC (6 decimals) to deposit
    /// @return usycReceived Amount of USYC shares minted
    function deposit(uint256 usdcAmount) external returns (uint256 usycReceived);

    /// @notice Redeem USYC shares for USDC
    /// @param usycAmount Amount of USYC shares to redeem
    /// @return usdcReceived Amount of USDC returned
    function redeem(uint256 usycAmount) external returns (uint256 usdcReceived);

    /// @notice Current exchange rate: USDC per USYC share (18 decimals)
    function exchangeRate() external view returns (uint256);

    /// @notice Check if address is eligible to deposit
    function isEligible(address account) external view returns (bool);
}

interface IUSYC {
    function balanceOf(address account) external view returns (uint256);
    function approve(address spender, uint256 amount) external returns (bool);
}

interface IUSYCEntitlements {
    function isEntitled(address account, bytes32 role) external view returns (bool);
}
