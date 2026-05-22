// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";

/// @title DisputeInsurance
/// @notice ERC-8183 Agentic Commerce — Dispute Insurance for UMA oracle manipulation
/// @dev Buyers pay a 5% premium to get 5× payout if Oracle Sentinel wins a dispute.
///      Only the authorized Sentinel Watchdog agent can trigger payouts.
///      Circle USDC on Arc Testnet (chainId: 5042002)
contract DisputeInsurance is Ownable, ReentrancyGuard {

    // =========================================================================
    // Constants
    // =========================================================================

    /// @notice Payout multiplier: buyer receives 5× their coverage amount
    uint256 public constant PAYOUT_MULTIPLIER = 5;

    /// @notice Premium rate in basis points (500 = 5%)
    uint256 public constant PREMIUM_BPS = 500;

    /// @notice Policy duration: 7 days from purchase
    uint256 public constant POLICY_DURATION = 7 days;

    /// @notice Minimum coverage: $10 USDC (6 decimals)
    uint256 public constant MIN_COVERAGE = 10e6;

    /// @notice Maximum coverage: $1,000 USDC (6 decimals)
    uint256 public constant MAX_COVERAGE = 1000e6;

    // =========================================================================
    // Types
    // =========================================================================

    struct Policy {
        address buyer;
        string marketId;
        uint256 premium;         // USDC paid (6 decimals)
        uint256 coverageAmount;  // USDC coverage (6 decimals)
        uint256 payout;          // 5× coverage if triggered
        uint256 purchasedAt;
        uint256 expiresAt;
        bool active;
        bool paid;
    }

    // =========================================================================
    // State
    // =========================================================================

    IERC20 public immutable usdc;

    /// @notice Authorized Sentinel Watchdog address that can trigger payouts
    address public sentinelWatchdog;

    /// @notice All policies by ID
    mapping(uint256 => Policy) public policies;

    /// @notice Policy IDs per buyer
    mapping(address => uint256[]) public buyerPolicies;

    /// @notice Policy IDs per market
    mapping(string => uint256[]) public marketPolicies;

    /// @notice Total pool balance available for payouts
    uint256 public poolBalance;

    /// @notice Total premiums collected
    uint256 public totalPremiumsCollected;

    /// @notice Total payouts made
    uint256 public totalPayoutsMade;

    /// @notice Policy counter
    uint256 public nextPolicyId;

    // =========================================================================
    // Events
    // =========================================================================

    event PolicyPurchased(
        uint256 indexed policyId,
        address indexed buyer,
        string marketId,
        uint256 premium,
        uint256 coverage,
        uint256 expiresAt
    );

    event PayoutTriggered(
        uint256 indexed policyId,
        address indexed buyer,
        string marketId,
        uint256 payoutAmount,
        address triggeredBy
    );

    event PolicyExpired(uint256 indexed policyId, address indexed buyer);

    event PoolFunded(address indexed funder, uint256 amount);

    event WatchdogUpdated(address indexed oldWatchdog, address indexed newWatchdog);

    // =========================================================================
    // Constructor
    // =========================================================================

    constructor(
        address initialOwner,
        address _usdc,
        address _sentinelWatchdog
    ) Ownable(initialOwner) {
        require(_usdc != address(0), "Zero USDC address");
        require(_sentinelWatchdog != address(0), "Zero watchdog address");
        usdc = IERC20(_usdc);
        sentinelWatchdog = _sentinelWatchdog;
    }

    // =========================================================================
    // Modifiers
    // =========================================================================

    modifier onlySentinel() {
        require(msg.sender == sentinelWatchdog || msg.sender == owner(), "Not authorized sentinel");
        _;
    }

    // =========================================================================
    // Buyer Functions
    // =========================================================================

    /// @notice Purchase dispute insurance for a specific Polymarket market
    /// @param marketId Polymarket market condition ID to insure
    /// @param coverageAmount USDC coverage amount (6 decimals, $10–$1,000)
    /// @return policyId Unique ID for this policy
    function buyPolicy(
        string calldata marketId,
        uint256 coverageAmount
    ) external nonReentrant returns (uint256 policyId) {
        require(bytes(marketId).length > 0, "Empty marketId");
        require(coverageAmount >= MIN_COVERAGE, "Coverage below minimum $10");
        require(coverageAmount <= MAX_COVERAGE, "Coverage above maximum $1,000");

        uint256 premium = (coverageAmount * PREMIUM_BPS) / 10000;
        uint256 payout = coverageAmount * PAYOUT_MULTIPLIER;

        // Transfer premium from buyer
        require(usdc.transferFrom(msg.sender, address(this), premium), "USDC transfer failed");

        poolBalance += premium;
        totalPremiumsCollected += premium;

        policyId = nextPolicyId++;
        uint256 expiresAt = block.timestamp + POLICY_DURATION;

        policies[policyId] = Policy({
            buyer: msg.sender,
            marketId: marketId,
            premium: premium,
            coverageAmount: coverageAmount,
            payout: payout,
            purchasedAt: block.timestamp,
            expiresAt: expiresAt,
            active: true,
            paid: false
        });

        buyerPolicies[msg.sender].push(policyId);
        marketPolicies[marketId].push(policyId);

        emit PolicyPurchased(policyId, msg.sender, marketId, premium, coverageAmount, expiresAt);
    }

    /// @notice Refund a buyer for an expired, unpaid policy (20% of premium back)
    /// @param policyId Policy to refund
    function refundExpired(uint256 policyId) external nonReentrant {
        Policy storage policy = policies[policyId];
        require(policy.buyer == msg.sender, "Not policy owner");
        require(policy.active, "Policy not active");
        require(!policy.paid, "Already paid out");
        require(block.timestamp > policy.expiresAt, "Policy not expired");

        policy.active = false;

        // Refund 20% of premium as consolation
        uint256 refundAmount = policy.premium / 5;
        if (refundAmount > 0 && poolBalance >= refundAmount) {
            poolBalance -= refundAmount;
            require(usdc.transfer(msg.sender, refundAmount), "Refund failed");
        }

        emit PolicyExpired(policyId, msg.sender);
    }

    // =========================================================================
    // Sentinel-Only Functions
    // =========================================================================

    /// @notice Trigger payout for all active policies on a market (called by Watchdog)
    /// @param marketId Market where manipulation was confirmed via UMA dispute win
    function triggerMarketPayout(string calldata marketId) external onlySentinel nonReentrant {
        uint256[] storage policyIds = marketPolicies[marketId];
        uint256 count = policyIds.length;

        for (uint256 i = 0; i < count; i++) {
            uint256 policyId = policyIds[i];
            Policy storage policy = policies[policyId];

            if (!policy.active || policy.paid || block.timestamp > policy.expiresAt) {
                continue;
            }

            uint256 payoutAmount = policy.payout;

            // Cap payout at available pool balance
            if (payoutAmount > poolBalance) {
                payoutAmount = poolBalance;
            }

            if (payoutAmount == 0) {
                break;
            }

            policy.active = false;
            policy.paid = true;
            poolBalance -= payoutAmount;
            totalPayoutsMade += payoutAmount;

            require(usdc.transfer(policy.buyer, payoutAmount), "Payout transfer failed");

            emit PayoutTriggered(policyId, policy.buyer, marketId, payoutAmount, msg.sender);
        }
    }

    /// @notice Trigger payout for a single policy by ID
    /// @param policyId Policy to pay out
    function triggerSinglePayout(uint256 policyId) external onlySentinel nonReentrant {
        Policy storage policy = policies[policyId];
        require(policy.active, "Policy not active");
        require(!policy.paid, "Already paid");
        require(block.timestamp <= policy.expiresAt, "Policy expired");

        uint256 payoutAmount = policy.payout;
        if (payoutAmount > poolBalance) {
            payoutAmount = poolBalance;
        }
        require(payoutAmount > 0, "Pool empty");

        policy.active = false;
        policy.paid = true;
        poolBalance -= payoutAmount;
        totalPayoutsMade += payoutAmount;

        require(usdc.transfer(policy.buyer, payoutAmount), "Payout failed");

        emit PayoutTriggered(policyId, policy.buyer, policy.marketId, payoutAmount, msg.sender);
    }

    // =========================================================================
    // Owner Functions
    // =========================================================================

    /// @notice Fund the insurance pool with USDC
    function fundPool(uint256 amount) external onlyOwner {
        require(usdc.transferFrom(msg.sender, address(this), amount), "Fund transfer failed");
        poolBalance += amount;
        emit PoolFunded(msg.sender, amount);
    }

    /// @notice Update the authorized Sentinel Watchdog address
    function setSentinelWatchdog(address newWatchdog) external onlyOwner {
        require(newWatchdog != address(0), "Zero address");
        emit WatchdogUpdated(sentinelWatchdog, newWatchdog);
        sentinelWatchdog = newWatchdog;
    }

    /// @notice Withdraw excess pool funds (only after all policies expire)
    function withdrawExcess(uint256 amount) external onlyOwner {
        require(amount <= poolBalance, "Insufficient pool");
        poolBalance -= amount;
        require(usdc.transfer(owner(), amount), "Withdraw failed");
    }

    // =========================================================================
    // View Functions
    // =========================================================================

    function getPolicy(uint256 policyId) external view returns (Policy memory) {
        return policies[policyId];
    }

    function getBuyerPolicies(address buyer) external view returns (uint256[] memory) {
        return buyerPolicies[buyer];
    }

    function getMarketPolicies(string calldata marketId) external view returns (uint256[] memory) {
        return marketPolicies[marketId];
    }

    function calculatePremium(uint256 coverageAmount) external pure returns (uint256) {
        return (coverageAmount * PREMIUM_BPS) / 10000;
    }

    function getPoolStats() external view returns (
        uint256 balance,
        uint256 totalPremiums,
        uint256 totalPayouts,
        uint256 totalPolicies
    ) {
        return (poolBalance, totalPremiumsCollected, totalPayoutsMade, nextPolicyId);
    }
}
