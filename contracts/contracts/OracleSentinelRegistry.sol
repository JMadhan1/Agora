// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "./AttestationVault.sol";
import "./BondManager.sol";

/// @title OracleSentinelRegistry
/// @notice Central registry for all Oracle Sentinel agents and system statistics
/// @dev Circle Tool: ERC-8004 Agent Identity + ERC-8183 Agentic Commerce on Arc Testnet
///      Tracks agent profiles, job completion history, calibration accuracy, and
///      system-wide statistics used for Canteen traction dashboard.
contract OracleSentinelRegistry is Ownable, Pausable, ReentrancyGuard {

    // =========================================================================
    // Types
    // =========================================================================

    /// @notice Complete profile for a registered Oracle Sentinel agent
    struct AgentProfile {
        /// @notice Agent's operating wallet address
        address wallet;
        /// @notice Agent role: "scout" | "judge" | "watchdog"
        string agentType;
        /// @notice IPFS URI of ERC-8004 identity metadata JSON
        string erc8004MetadataUri;
        /// @notice Total number of Oracle Sentinel jobs completed
        uint256 jobsCompleted;
        /// @notice Number of predictions that matched actual market resolution
        uint256 correctCalls;
        /// @notice Current USDC bond held in BondManager (6-decimal units)
        uint256 bondAmount;
        /// @notice Whether agent is currently active
        bool active;
        /// @notice Unix timestamp of initial registration
        uint256 registeredAt;
    }

    // =========================================================================
    // State
    // =========================================================================

    /// @notice Agent profiles indexed by wallet address
    mapping(address => AgentProfile) public agents;

    /// @notice Ordered list of all registered agent addresses
    address[] public agentList;

    /// @notice Authorized callers for recordJobCompletion (agent wallets + owner)
    mapping(address => bool) public authorized;

    /// @notice Reference to AttestationVault for attestation counts
    AttestationVault public vault;

    /// @notice Reference to BondManager for bond status
    BondManager public bondManager;

    // System-wide statistics
    /// @notice Total attestations committed across all agents
    uint256 public totalAttestations;
    /// @notice Total verification jobs completed
    uint256 public totalJobsCompleted;
    /// @notice Total UMA disputes triggered by Watchdog
    uint256 public totalDisputesTriggered;
    /// @notice Total disputes won (resolved in Sentinel's favor)
    uint256 public totalDisputesWon;

    // =========================================================================
    // Events
    // =========================================================================

    event AgentRegistered(address indexed agent, string agentType, string metadataUri);
    event JobCompleted(address indexed agent, string marketId, bool correct);
    event DisputeOutcome(string marketId, bool won, uint256 reward);
    event AuthorizationChanged(address indexed caller, bool authorized);

    // =========================================================================
    // Constructor
    // =========================================================================

    constructor(
        address initialOwner,
        address _vault,
        address _bondManager
    ) Ownable(initialOwner) {
        require(_vault != address(0), "Zero vault");
        require(_bondManager != address(0), "Zero bondManager");
        vault = AttestationVault(_vault);
        bondManager = BondManager(_bondManager);
        authorized[initialOwner] = true;
    }

    // =========================================================================
    // Modifiers
    // =========================================================================

    modifier onlyAuthorized() {
        require(authorized[msg.sender] || msg.sender == owner(), "Not authorized");
        _;
    }

    // =========================================================================
    // Owner Functions
    // =========================================================================

    function setAuthorized(address caller, bool auth) external onlyOwner {
        authorized[caller] = auth;
        emit AuthorizationChanged(caller, auth);
    }

    function pause() external onlyOwner { _pause(); }
    function unpause() external onlyOwner { _unpause(); }

    // =========================================================================
    // Registration
    // =========================================================================

    /// @notice Register a new Oracle Sentinel agent
    /// @dev Requires prior USDC approval to BondManager for MINIMUM_BOND (10 USDC)
    ///      Circle Tool: Arc Testnet — agent identity anchored on-chain
    /// @param agentType Role string: "scout" | "judge" | "watchdog"
    /// @param metadataUri IPFS URI of ERC-8004 identity metadata
    function registerAgent(
        string calldata agentType,
        string calldata metadataUri
    ) external whenNotPaused nonReentrant {
        require(bytes(agentType).length > 0, "Empty agent type");
        require(bytes(metadataUri).length > 0, "Empty metadata URI");
        require(!agents[msg.sender].active, "Already registered");

        // Deposit bond to BondManager — agent must have pre-approved USDC spend
        bondManager.depositBond();

        AgentProfile memory profile = AgentProfile({
            wallet: msg.sender,
            agentType: agentType,
            erc8004MetadataUri: metadataUri,
            jobsCompleted: 0,
            correctCalls: 0,
            bondAmount: bondManager.getBond(msg.sender),
            active: true,
            registeredAt: block.timestamp
        });

        agents[msg.sender] = profile;
        agentList.push(msg.sender);

        emit AgentRegistered(msg.sender, agentType, metadataUri);
    }

    // =========================================================================
    // Job Tracking
    // =========================================================================

    /// @notice Record the outcome of a completed verification job
    /// @param agent Agent wallet that completed the job
    /// @param marketId Polymarket market condition ID
    /// @param correct Whether the agent's prediction matched actual resolution
    function recordJobCompletion(
        address agent,
        string calldata marketId,
        bool correct
    ) external onlyAuthorized whenNotPaused {
        require(agents[agent].active, "Agent not registered");

        agents[agent].jobsCompleted++;
        if (correct) {
            agents[agent].correctCalls++;
        }
        totalJobsCompleted++;

        emit JobCompleted(agent, marketId, correct);
    }

    /// @notice Record the outcome of a dispute
    /// @param marketId Polymarket market condition ID
    /// @param won Whether the dispute was resolved in Sentinel's favor
    /// @param reward USDC reward received (0 if lost)
    function recordDisputeOutcome(
        string calldata marketId,
        bool won,
        uint256 reward
    ) external onlyAuthorized {
        totalDisputesTriggered++;
        if (won) {
            totalDisputesWon++;
        }
        emit DisputeOutcome(marketId, won, reward);
    }

    /// @notice Increment global attestation counter (called by authorized agents)
    function incrementAttestations() external onlyAuthorized {
        totalAttestations++;
    }

    // =========================================================================
    // View Functions
    // =========================================================================

    /// @notice Get an agent's calibration rate in basis points (0–10000)
    /// @param agent Agent wallet address
    /// @return bps Calibration rate: 10000 = 100%, 7500 = 75%, etc.
    function getCalibrationRate(address agent) external view returns (uint256 bps) {
        AgentProfile storage profile = agents[agent];
        if (profile.jobsCompleted == 0) return 0;
        return (profile.correctCalls * 10000) / profile.jobsCompleted;
    }

    /// @notice Get top N agents sorted by calibration rate descending
    /// @param limit Maximum number of agents to return
    /// @return Top agents by calibration accuracy
    function getTopAgents(uint8 limit) external view returns (AgentProfile[] memory) {
        uint256 count = agentList.length < limit ? agentList.length : limit;
        AgentProfile[] memory top = new AgentProfile[](count);

        // Copy active agents
        uint256 activeCount = 0;
        address[] memory activeAddrs = new address[](agentList.length);
        for (uint256 i = 0; i < agentList.length; i++) {
            if (agents[agentList[i]].active) {
                activeAddrs[activeCount] = agentList[i];
                activeCount++;
            }
        }

        // Simple insertion sort on calibration rate (small arrays — O(n²) fine here)
        for (uint256 i = 0; i < activeCount; i++) {
            for (uint256 j = i + 1; j < activeCount; j++) {
                uint256 rateI = agents[activeAddrs[i]].jobsCompleted > 0
                    ? (agents[activeAddrs[i]].correctCalls * 10000) / agents[activeAddrs[i]].jobsCompleted
                    : 0;
                uint256 rateJ = agents[activeAddrs[j]].jobsCompleted > 0
                    ? (agents[activeAddrs[j]].correctCalls * 10000) / agents[activeAddrs[j]].jobsCompleted
                    : 0;
                if (rateJ > rateI) {
                    address tmp = activeAddrs[i];
                    activeAddrs[i] = activeAddrs[j];
                    activeAddrs[j] = tmp;
                }
            }
        }

        uint256 returnCount = activeCount < count ? activeCount : count;
        for (uint256 i = 0; i < returnCount; i++) {
            top[i] = agents[activeAddrs[i]];
        }
        return top;
    }

    /// @notice Get system-wide statistics for the Canteen traction dashboard
    /// @return attestations Total attestations committed
    /// @return jobs Total verification jobs completed
    /// @return disputes Total UMA disputes triggered
    /// @return wins Total disputes won
    function getSystemStats()
        external
        view
        returns (
            uint256 attestations,
            uint256 jobs,
            uint256 disputes,
            uint256 wins
        )
    {
        return (totalAttestations, totalJobsCompleted, totalDisputesTriggered, totalDisputesWon);
    }

    /// @notice Get total number of registered agents
    function getAgentCount() external view returns (uint256) {
        return agentList.length;
    }
}
