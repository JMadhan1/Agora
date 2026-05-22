// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title IAgenticCommerce
/// @notice ERC-8183 Agentic Commerce interface for job creation and settlement on Arc
/// @dev Contract: 0x0747EEf0706327138c69792bF28Cd525089e4583
interface IAgenticCommerce {
    enum JobStatus { CREATED, FUNDED, AGENT_ASSIGNED, DELIVERABLE_SUBMITTED, COMPLETED, FAILED }

    struct Job {
        bytes32 jobId;
        address client;
        address assignedAgent;
        string description;
        uint256 budgetUsdc;
        uint256 deadline;
        JobStatus status;
        bytes32 deliverableHash;
        string deliverableCid;
        uint256 createdAt;
        uint256 completedAt;
    }

    event JobCreated(bytes32 indexed jobId, address indexed client, uint256 budget, uint256 deadline);
    event JobFunded(bytes32 indexed jobId, uint256 amount);
    event AgentAssigned(bytes32 indexed jobId, address indexed agent);
    event DeliverableSubmitted(bytes32 indexed jobId, bytes32 deliverableHash, string cid);
    event JobCompleted(bytes32 indexed jobId, address indexed agent, uint256 payout);
    event JobFailed(bytes32 indexed jobId, string reason);

    /// @notice Create a new job with USDC escrow
    function createJob(
        string calldata description,
        uint256 budgetUsdc,
        uint256 deadlineTimestamp
    ) external returns (bytes32 jobId);

    /// @notice Agent submits work deliverable
    function submitDeliverable(
        bytes32 jobId,
        bytes32 deliverableHash,
        string calldata deliverableCid
    ) external;

    /// @notice Client or evaluator releases payment to agent
    function completeJob(bytes32 jobId) external;

    /// @notice Mark job as failed, refund client
    function failJob(bytes32 jobId, string calldata reason) external;

    /// @notice Get job details
    function getJob(bytes32 jobId) external view returns (Job memory);

    /// @notice Get jobs by client address
    function getJobsByClient(address client) external view returns (bytes32[] memory);
}
