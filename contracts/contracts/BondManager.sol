// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";
import "./interfaces/IUSDC.sol";

/// @title BondManager
/// @notice Manages USDC bonds for Oracle Sentinel agents
/// @dev Circle Tool: Arc Testnet USDC (0x3600000000000000000000000000000000000000)
///      Agents must post a USDC bond to operate. Bonds are slashed for provably wrong
///      attestations. Dispute winners receive a share of slashed bonds.
contract BondManager is Ownable, ReentrancyGuard, Pausable {

    // =========================================================================
    // Constants
    // =========================================================================

    /// @notice Circle Tool: Arc Testnet USDC — 6 decimals
    address public constant USDC_TOKEN = 0x3600000000000000000000000000000000000000;

    /// @notice Minimum bond required to operate as an agent (10 USDC)
    uint256 public constant MINIMUM_BOND = 10 * 1e6;

    // =========================================================================
    // State
    // =========================================================================

    /// @notice USDC bond amounts per agent address (6-decimal units)
    mapping(address => uint256) public bonds;

    /// @notice Number of times each agent has been slashed
    mapping(address => uint256) public slashCount;

    /// @notice Pending USDC rewards for dispute winners
    mapping(address => uint256) public disputeRewards;

    /// @notice Total USDC slashed across all agents
    uint256 public totalSlashed;

    /// @notice AttestationVault address — only vault can trigger slashes
    address public attestationVault;

    // =========================================================================
    // Events
    // =========================================================================

    /// @notice Emitted when an agent deposits a USDC bond
    event BondDeposited(address indexed agent, uint256 amount);

    /// @notice Emitted when an agent's bond is slashed for bad attestation
    event BondSlashed(address indexed agent, uint256 amount, string reason);

    /// @notice Emitted when a dispute winner claims their USDC reward
    event RewardClaimed(address indexed winner, uint256 amount);

    /// @notice Emitted when AttestationVault address is updated
    event VaultUpdated(address indexed newVault);

    // =========================================================================
    // Constructor
    // =========================================================================

    constructor(address initialOwner, address _attestationVault) Ownable(initialOwner) {
        require(_attestationVault != address(0), "Zero vault address");
        attestationVault = _attestationVault;
    }

    // =========================================================================
    // Modifiers
    // =========================================================================

    /// @notice Only the AttestationVault contract can call slashBond and addDisputeReward
    modifier onlyVault() {
        require(msg.sender == attestationVault, "Only vault");
        _;
    }

    // =========================================================================
    // Owner Functions
    // =========================================================================

    /// @notice Update the AttestationVault address
    function setVault(address newVault) external onlyOwner {
        require(newVault != address(0), "Zero address");
        attestationVault = newVault;
        emit VaultUpdated(newVault);
    }

    function pause() external onlyOwner { _pause(); }
    function unpause() external onlyOwner { _unpause(); }

    // =========================================================================
    // Bond Management
    // =========================================================================

    /// @notice Deposit USDC bond to register as an active Oracle Sentinel agent
    /// @dev Caller must approve this contract to spend USDC before calling
    ///      Circle Tool: Arc Testnet USDC transfer via ERC-20 transferFrom
    function depositBond() external whenNotPaused nonReentrant {
        uint256 amount = MINIMUM_BOND;
        require(
            IUSDC(USDC_TOKEN).transferFrom(msg.sender, address(this), amount),
            "USDC transfer failed"
        );
        bonds[msg.sender] += amount;
        emit BondDeposited(msg.sender, amount);
    }

    /// @notice Deposit a custom bond amount (must be >= MINIMUM_BOND)
    /// @param amount USDC amount in 6-decimal units
    function depositBondAmount(uint256 amount) external whenNotPaused nonReentrant {
        require(amount >= MINIMUM_BOND, "Below minimum bond");
        require(
            IUSDC(USDC_TOKEN).transferFrom(msg.sender, address(this), amount),
            "USDC transfer failed"
        );
        bonds[msg.sender] += amount;
        emit BondDeposited(msg.sender, amount);
    }

    /// @notice Slash an agent's bond for a provably wrong or manipulative attestation
    /// @dev Only callable by AttestationVault. Never slashes more than current bond.
    /// @param agent Address of the agent to slash
    /// @param amount USDC amount to slash (6-decimal units)
    /// @param reason Human-readable reason for slash
    function slashBond(
        address agent,
        uint256 amount,
        string calldata reason
    ) external onlyVault whenNotPaused nonReentrant {
        require(agent != address(0), "Zero agent address");
        // Never slash more than the agent's current bond
        uint256 slashAmount = amount > bonds[agent] ? bonds[agent] : amount;
        if (slashAmount == 0) return;

        bonds[agent] -= slashAmount;
        totalSlashed += slashAmount;
        slashCount[agent]++;

        emit BondSlashed(agent, slashAmount, reason);
    }

    /// @notice Add USDC dispute reward for a winning challenger
    /// @dev Called by AttestationVault when a dispute is resolved in challenger's favor
    function addDisputeReward(address winner, uint256 amount) external onlyVault {
        require(winner != address(0), "Zero address");
        require(amount > 0, "Zero reward");
        disputeRewards[winner] += amount;
    }

    /// @notice Claim accumulated USDC dispute rewards
    function claimReward() external nonReentrant {
        uint256 reward = disputeRewards[msg.sender];
        require(reward > 0, "No reward to claim");
        disputeRewards[msg.sender] = 0;
        require(
            IUSDC(USDC_TOKEN).transfer(msg.sender, reward),
            "USDC transfer failed"
        );
        emit RewardClaimed(msg.sender, reward);
    }

    // =========================================================================
    // View Functions
    // =========================================================================

    /// @notice Get an agent's current USDC bond (6-decimal units)
    function getBond(address agent) external view returns (uint256) {
        return bonds[agent];
    }

    /// @notice Check if an agent has sufficient bond to operate
    function isBondSufficient(address agent) external view returns (bool) {
        return bonds[agent] >= MINIMUM_BOND;
    }

    /// @notice Get an agent's pending dispute reward
    function getPendingReward(address agent) external view returns (uint256) {
        return disputeRewards[agent];
    }
}
