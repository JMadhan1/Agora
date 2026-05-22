// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/// @title AttestationVault
/// @notice Immutable on-chain commitment of Oracle Sentinel reasoning trace hashes
/// @dev Circle Tool: Arc Testnet — $0.01/attestation makes this economically viable
///      Each attestation links a SHA-256 hash of the full reasoning trace JSON
///      to an IPFS CID where the complete trace is stored.
///      Deployed on Arc Testnet (chainId: 5042002)
contract AttestationVault is Ownable, Pausable, ReentrancyGuard {

    // =========================================================================
    // Types
    // =========================================================================

    /// @notice A single oracle verdict committed on-chain
    struct Attestation {
        /// @notice SHA-256 hash of the full reasoning trace JSON stored on IPFS
        bytes32 traceHash;
        /// @notice IPFS CID where full reasoning trace is stored
        string ipfsCid;
        /// @notice Polymarket market ID this attestation covers
        string marketId;
        /// @notice Confidence score 0–100 (maps to 0%–100%)
        uint8 confidence;
        /// @notice Unix timestamp of attestation
        uint256 timestamp;
        /// @notice Authorized agent wallet that committed this attestation
        address agentAddress;
        /// @notice True if this attestation has been flagged as disputed
        bool disputed;
    }

    // =========================================================================
    // State
    // =========================================================================

    /// @notice All attestations indexed by Polymarket market ID
    mapping(string => Attestation[]) public marketAttestations;

    /// @notice Deduplication: true if this trace hash has already been committed
    mapping(bytes32 => bool) public hashExists;

    /// @notice Wallets authorized to commit attestations and flag disputes
    mapping(address => bool) public authorizedAgents;

    /// @notice Total number of attestations committed across all markets
    uint256 public totalAttestations;

    // =========================================================================
    // Events
    // =========================================================================

    /// @notice Emitted when a new attestation is committed
    event AttestationCommitted(
        string indexed marketId,
        bytes32 traceHash,
        string ipfsCid,
        uint8 confidence,
        address indexed agent,
        uint256 timestamp
    );

    /// @notice Emitted when an attestation is flagged as a potential manipulation
    event DisputeFlagged(
        string indexed marketId,
        bytes32 traceHash,
        string reason,
        address indexed flaggedBy
    );

    /// @notice Emitted when an agent is authorized or deauthorized
    event AgentAuthorizationChanged(address indexed agent, bool authorized);

    // =========================================================================
    // Constructor
    // =========================================================================

    constructor(address initialOwner) Ownable(initialOwner) {}

    // =========================================================================
    // Modifiers
    // =========================================================================

    /// @notice Restricts function to authorized agent wallets
    modifier onlyAuthorizedAgent() {
        require(authorizedAgents[msg.sender], "Not authorized agent");
        _;
    }

    // =========================================================================
    // Owner Functions
    // =========================================================================

    /// @notice Authorize an agent wallet to commit attestations
    /// @param agent Wallet address of the agent to authorize
    function addAgent(address agent) external onlyOwner {
        require(agent != address(0), "Zero address");
        authorizedAgents[agent] = true;
        emit AgentAuthorizationChanged(agent, true);
    }

    /// @notice Revoke an agent's authorization
    /// @param agent Wallet address of the agent to deauthorize
    function removeAgent(address agent) external onlyOwner {
        authorizedAgents[agent] = false;
        emit AgentAuthorizationChanged(agent, false);
    }

    /// @notice Emergency pause — stops all attestation writes
    function pause() external onlyOwner {
        _pause();
    }

    /// @notice Resume normal operation after emergency pause
    function unpause() external onlyOwner {
        _unpause();
    }

    // =========================================================================
    // Core Functions
    // =========================================================================

    /// @notice Commit a verified reasoning trace hash on-chain
    /// @dev Circle Tool: Arc Testnet — each call costs ~$0.01 in USDC gas fees
    ///      The traceHash is SHA-256(JSON.stringify(reasoningTrace, sorted_keys))
    ///      The full trace is stored off-chain on IPFS at ipfsCid
    /// @param marketId Polymarket market condition ID
    /// @param traceHash SHA-256 hash of reasoning trace JSON (bytes32)
    /// @param ipfsCid IPFS CID where full reasoning trace is stored
    /// @param confidence Oracle confidence score 0–100
    function commitAttestation(
        string calldata marketId,
        bytes32 traceHash,
        string calldata ipfsCid,
        uint8 confidence
    ) external onlyAuthorizedAgent whenNotPaused nonReentrant {
        require(bytes(marketId).length > 0, "Empty marketId");
        require(traceHash != bytes32(0), "Zero hash");
        require(bytes(ipfsCid).length > 0, "Empty IPFS CID");
        require(confidence <= 100, "Confidence > 100");
        // Deduplication: each reasoning trace can only be committed once
        require(!hashExists[traceHash], "Hash already committed");

        hashExists[traceHash] = true;

        Attestation memory attestation = Attestation({
            traceHash: traceHash,
            ipfsCid: ipfsCid,
            marketId: marketId,
            confidence: confidence,
            timestamp: block.timestamp,
            agentAddress: msg.sender,
            disputed: false
        });

        // Circle Tool: Arc Testnet — append to market's attestation history
        marketAttestations[marketId].push(attestation);
        totalAttestations++;

        emit AttestationCommitted(
            marketId,
            traceHash,
            ipfsCid,
            confidence,
            msg.sender,
            block.timestamp
        );
    }

    /// @notice Flag an existing attestation as disputed (potential manipulation detected)
    /// @dev Called by Watchdog agent when UMA resolution deviates >40% from our estimate
    /// @param marketId Polymarket market condition ID
    /// @param traceHash SHA-256 hash identifying the attestation to flag
    /// @param reason Human-readable reason for the dispute flag
    function flagDispute(
        string calldata marketId,
        bytes32 traceHash,
        string calldata reason
    ) external onlyAuthorizedAgent whenNotPaused {
        require(hashExists[traceHash], "Hash not found");
        require(bytes(reason).length > 0, "Empty reason");

        Attestation[] storage attestations = marketAttestations[marketId];
        bool found = false;
        for (uint256 i = 0; i < attestations.length; i++) {
            if (attestations[i].traceHash == traceHash) {
                attestations[i].disputed = true;
                found = true;
                break;
            }
        }
        require(found, "Attestation not found for market");

        emit DisputeFlagged(marketId, traceHash, reason, msg.sender);
    }

    // =========================================================================
    // View Functions
    // =========================================================================

    /// @notice Get all attestations for a market
    /// @param marketId Polymarket market condition ID
    /// @return Array of all attestations for this market, ordered chronologically
    function getAttestations(string calldata marketId)
        external
        view
        returns (Attestation[] memory)
    {
        return marketAttestations[marketId];
    }

    /// @notice Get the most recent attestation for a market
    /// @dev Reverts if no attestations exist for this market
    /// @param marketId Polymarket market condition ID
    /// @return The latest Attestation struct
    function getLatestAttestation(string calldata marketId)
        external
        view
        returns (Attestation memory)
    {
        Attestation[] storage attestations = marketAttestations[marketId];
        require(attestations.length > 0, "No attestations for market");
        return attestations[attestations.length - 1];
    }

    /// @notice Get the number of attestations for a market
    /// @param marketId Polymarket market condition ID
    /// @return Number of attestations committed for this market
    function getAttestationCount(string calldata marketId)
        external
        view
        returns (uint256)
    {
        return marketAttestations[marketId].length;
    }

    /// @notice Check if an agent is authorized
    /// @param agent Wallet address to check
    /// @return True if agent is authorized to commit attestations
    function isAuthorized(address agent) external view returns (bool) {
        return authorizedAgents[agent];
    }
}
