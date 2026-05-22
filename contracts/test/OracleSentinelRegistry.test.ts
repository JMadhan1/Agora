// =============================================================================
// FILE: contracts/test/OracleSentinelRegistry.test.ts
// =============================================================================
// Tests for OracleSentinelRegistry.sol
//
// Dependency chain:
//   MockERC20 (at hardcoded USDC address)
//     └─ BondManager  (depositBond pulls from USDC)
//         └─ AttestationVault
//             └─ OracleSentinelRegistry  (holds vault + bondManager refs)
//
// The same hardhat_setCode trick used in BondManager.test.ts is applied here
// so the registry's internal bondManager.depositBond() call resolves correctly.
// =============================================================================

import { expect }                from "chai";
import { ethers, network }       from "hardhat";
import { anyValue }              from "@nomicfoundation/hardhat-chai-matchers/withArgs";
import type { SignerWithAddress } from "@nomicfoundation/hardhat-ethers/signers";
import type {
  AttestationVault,
  BondManager,
  MockERC20,
  OracleSentinelRegistry,
} from "../typechain-types";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const USDC_HARDCODED = "0x3600000000000000000000000000000000000000";
const MINIMUM_BOND   = 10n * 1_000_000n; // 10 USDC, 6 decimals

const AGENT_TYPE     = "scout";
const METADATA_URI   = "ipfs://QmAgentMetadata1234";
const MARKET_ID      = "0xdeadbeef-market";

// ---------------------------------------------------------------------------
// Helper: deploy MockERC20 bytecode at the hardcoded USDC address
// ---------------------------------------------------------------------------

async function deployMockAtUsdcAddress(): Promise<MockERC20> {
  const factory  = await ethers.getContractFactory("MockERC20");
  const mock     = await factory.deploy("Mock USDC", "USDC", 6);
  await mock.waitForDeployment();
  const code     = await ethers.provider.getCode(await mock.getAddress());
  await network.provider.send("hardhat_setCode", [USDC_HARDCODED, code]);
  return factory.attach(USDC_HARDCODED) as unknown as MockERC20;
}

// ---------------------------------------------------------------------------
// Helper: fund an agent and make it approve BondManager for MINIMUM_BOND
// ---------------------------------------------------------------------------

async function fundAndApprove(
  usdc:        MockERC20,
  bondManager: BondManager,
  agent:       SignerWithAddress,
  extraUSDC:   bigint = 0n
) {
  const total = MINIMUM_BOND + extraUSDC;
  await usdc.mint(agent.address, total);
  await usdc
    .connect(agent)
    .approve(await bondManager.getAddress(), MINIMUM_BOND);
}

// ---------------------------------------------------------------------------
// Suite
// ---------------------------------------------------------------------------

describe("OracleSentinelRegistry", () => {
  let registry:    OracleSentinelRegistry;
  let vault:       AttestationVault;
  let bondManager: BondManager;
  let usdc:        MockERC20;

  let owner:    SignerWithAddress;
  let agent1:   SignerWithAddress;
  let agent2:   SignerWithAddress;
  let agent3:   SignerWithAddress;
  let stranger: SignerWithAddress;

  beforeEach(async () => {
    [owner, agent1, agent2, agent3, stranger] = await ethers.getSigners();

    // 1. Deploy MockERC20 at hardcoded USDC address
    usdc = await deployMockAtUsdcAddress();

    // 2. Deploy AttestationVault
    vault = await ethers.deployContract("AttestationVault", [
      owner.address,
    ]) as unknown as AttestationVault;

    // 3. Deploy BondManager pointing at the vault
    bondManager = await ethers.deployContract("BondManager", [
      owner.address,
      await vault.getAddress(),
    ]) as unknown as BondManager;

    // 4. Deploy OracleSentinelRegistry
    registry = await ethers.deployContract("OracleSentinelRegistry", [
      owner.address,
      await vault.getAddress(),
      await bondManager.getAddress(),
    ]) as unknown as OracleSentinelRegistry;
  });

  // =========================================================================
  // 1. Deployment
  // =========================================================================

  describe("Deployment", () => {
    it("sets vault address correctly", async () => {
      expect(await registry.vault()).to.equal(await vault.getAddress());
    });

    it("sets bondManager address correctly", async () => {
      expect(await registry.bondManager()).to.equal(await bondManager.getAddress());
    });

    it("sets initialOwner correctly", async () => {
      expect(await registry.owner()).to.equal(owner.address);
    });

    it("owner is authorized by default", async () => {
      expect(await registry.authorized(owner.address)).to.be.true;
    });

    it("all system stats start at zero", async () => {
      const [attestations, jobs, disputes, wins] = await registry.getSystemStats();
      expect(attestations).to.equal(0n);
      expect(jobs).to.equal(0n);
      expect(disputes).to.equal(0n);
      expect(wins).to.equal(0n);
    });

    it("reverts with 'Zero vault' for zero vault address", async () => {
      await expect(
        ethers.deployContract("OracleSentinelRegistry", [
          owner.address,
          ethers.ZeroAddress,
          await bondManager.getAddress(),
        ])
      ).to.be.revertedWith("Zero vault");
    });

    it("reverts with 'Zero bondManager' for zero bondManager address", async () => {
      await expect(
        ethers.deployContract("OracleSentinelRegistry", [
          owner.address,
          await vault.getAddress(),
          ethers.ZeroAddress,
        ])
      ).to.be.revertedWith("Zero bondManager");
    });
  });

  // =========================================================================
  // 2. registerAgent — happy path
  // =========================================================================

  describe("registerAgent", () => {
    it("creates agent profile after bond deposit", async () => {
      // Design note: registry.registerAgent() calls bondManager.depositBond()
      // internally.  Inside depositBond, msg.sender == the registry address, so
      // the USDC transferFrom pulls from the registry, not from agent1.
      // We therefore: (1) mint USDC to the registry, (2) impersonate the registry
      // to grant the BondManager an allowance.  setupRegistryUsdcApproval()
      // encapsulates both steps.
      await setupRegistryUsdcApproval();

      await expect(
        registry.connect(agent1).registerAgent(AGENT_TYPE, METADATA_URI)
      ).to.emit(registry, "AgentRegistered");

      const profile = await registry.agents(agent1.address);
      expect(profile.active).to.be.true;
      expect(profile.agentType).to.equal(AGENT_TYPE);
      expect(profile.erc8004MetadataUri).to.equal(METADATA_URI);
      expect(profile.wallet).to.equal(agent1.address);
      expect(profile.jobsCompleted).to.equal(0n);
      expect(profile.correctCalls).to.equal(0n);
    });

    it("emits AgentRegistered with correct args", async () => {
      await setupRegistryUsdcApproval();

      await expect(
        registry.connect(agent1).registerAgent(AGENT_TYPE, METADATA_URI)
      )
        .to.emit(registry, "AgentRegistered")
        .withArgs(agent1.address, AGENT_TYPE, METADATA_URI);
    });

    it("adds agent to agentList", async () => {
      await setupRegistryUsdcApproval();
      await registry.connect(agent1).registerAgent(AGENT_TYPE, METADATA_URI);
      expect(await registry.getAgentCount()).to.equal(1n);
      expect(await registry.agentList(0)).to.equal(agent1.address);
    });
  });

  // =========================================================================
  // 3. registerAgent twice — reverts "Already registered"
  // =========================================================================

  describe("registerAgent — second registration reverts", () => {
    it("reverts with 'Already registered' on second call", async () => {
      await setupRegistryUsdcApproval(2); // mint enough for 2 deposits
      await registry.connect(agent1).registerAgent(AGENT_TYPE, METADATA_URI);

      // Second call — agent1.active is already true
      await expect(
        registry.connect(agent1).registerAgent(AGENT_TYPE, METADATA_URI)
      ).to.be.revertedWith("Already registered");
    });
  });

  // =========================================================================
  // 4. recordJobCompletion
  // =========================================================================

  describe("recordJobCompletion", () => {
    beforeEach(async () => {
      await setupRegistryUsdcApproval();
      await registry.connect(agent1).registerAgent(AGENT_TYPE, METADATA_URI);
    });

    it("increments jobsCompleted for the agent", async () => {
      await registry.connect(owner).recordJobCompletion(agent1.address, MARKET_ID, true);
      const profile = await registry.agents(agent1.address);
      expect(profile.jobsCompleted).to.equal(1n);
    });

    it("increments correctCalls when correct=true", async () => {
      await registry.connect(owner).recordJobCompletion(agent1.address, MARKET_ID, true);
      const profile = await registry.agents(agent1.address);
      expect(profile.correctCalls).to.equal(1n);
    });

    it("does not increment correctCalls when correct=false", async () => {
      await registry.connect(owner).recordJobCompletion(agent1.address, MARKET_ID, false);
      const profile = await registry.agents(agent1.address);
      expect(profile.jobsCompleted).to.equal(1n);
      expect(profile.correctCalls).to.equal(0n);
    });

    it("increments totalJobsCompleted", async () => {
      await registry.connect(owner).recordJobCompletion(agent1.address, MARKET_ID, true);
      const [, jobs] = await registry.getSystemStats();
      expect(jobs).to.equal(1n);
    });

    it("emits JobCompleted", async () => {
      await expect(
        registry.connect(owner).recordJobCompletion(agent1.address, MARKET_ID, true)
      )
        .to.emit(registry, "JobCompleted")
        .withArgs(agent1.address, MARKET_ID, true);
    });

    it("reverts for unregistered agent", async () => {
      await expect(
        registry.connect(owner).recordJobCompletion(stranger.address, MARKET_ID, true)
      ).to.be.revertedWith("Agent not registered");
    });

    it("reverts for unauthorized caller", async () => {
      await expect(
        registry.connect(stranger).recordJobCompletion(agent1.address, MARKET_ID, true)
      ).to.be.revertedWith("Not authorized");
    });

    // -----------------------------------------------------------------------
    // getCalibrationRate — 2/3 correct = 6666 bps
    // -----------------------------------------------------------------------

    it("getCalibrationRate returns correct bps for 2/3 correct jobs", async () => {
      await registry.connect(owner).recordJobCompletion(agent1.address, MARKET_ID, true);
      await registry.connect(owner).recordJobCompletion(agent1.address, MARKET_ID, true);
      await registry.connect(owner).recordJobCompletion(agent1.address, MARKET_ID, false);

      const bps = await registry.getCalibrationRate(agent1.address);
      // (2 * 10000) / 3 = 6666 (integer division)
      expect(bps).to.equal(6666n);
    });

    it("getCalibrationRate returns 0 when no jobs completed", async () => {
      expect(await registry.getCalibrationRate(agent1.address)).to.equal(0n);
    });

    it("getCalibrationRate returns 10000 for 100% correct", async () => {
      await registry.connect(owner).recordJobCompletion(agent1.address, MARKET_ID, true);
      await registry.connect(owner).recordJobCompletion(agent1.address, MARKET_ID, true);
      expect(await registry.getCalibrationRate(agent1.address)).to.equal(10000n);
    });

    it("getCalibrationRate returns 0 for 0% correct", async () => {
      await registry.connect(owner).recordJobCompletion(agent1.address, MARKET_ID, false);
      expect(await registry.getCalibrationRate(agent1.address)).to.equal(0n);
    });
  });

  // =========================================================================
  // 5. getTopAgents — sorted descending by calibration rate
  // =========================================================================

  describe("getTopAgents", () => {
    beforeEach(async () => {
      // Register three agents
      await setupRegistryUsdcApproval(3);
      await registry.connect(agent1).registerAgent("scout",    "ipfs://agent1");
      await registry.connect(agent2).registerAgent("judge",    "ipfs://agent2");
      await registry.connect(agent3).registerAgent("watchdog", "ipfs://agent3");

      // agent1: 1/2 correct  = 5000 bps
      await registry.connect(owner).recordJobCompletion(agent1.address, MARKET_ID, true);
      await registry.connect(owner).recordJobCompletion(agent1.address, MARKET_ID, false);

      // agent2: 3/3 correct  = 10000 bps
      await registry.connect(owner).recordJobCompletion(agent2.address, MARKET_ID, true);
      await registry.connect(owner).recordJobCompletion(agent2.address, MARKET_ID, true);
      await registry.connect(owner).recordJobCompletion(agent2.address, MARKET_ID, true);

      // agent3: 0/1 correct  = 0 bps
      await registry.connect(owner).recordJobCompletion(agent3.address, MARKET_ID, false);
    });

    it("returns agents sorted descending by calibration rate", async () => {
      const top = await registry.getTopAgents(3);
      expect(top.length).to.equal(3);
      expect(top[0].wallet).to.equal(agent2.address); // 10000 bps
      expect(top[1].wallet).to.equal(agent1.address); // 5000 bps
      expect(top[2].wallet).to.equal(agent3.address); // 0 bps
    });

    it("respects limit parameter", async () => {
      const top = await registry.getTopAgents(2);
      expect(top.length).to.equal(2);
      expect(top[0].wallet).to.equal(agent2.address);
      expect(top[1].wallet).to.equal(agent1.address);
    });

    it("returns fewer items than limit when not enough agents", async () => {
      const top = await registry.getTopAgents(10);
      expect(top.length).to.equal(3); // only 3 registered
    });

    it("returns empty array when limit is 0", async () => {
      const top = await registry.getTopAgents(0);
      expect(top.length).to.equal(0);
    });
  });

  // =========================================================================
  // 6. getSystemStats — correct counts after events
  // =========================================================================

  describe("getSystemStats", () => {
    beforeEach(async () => {
      await setupRegistryUsdcApproval(2);
      await registry.connect(agent1).registerAgent(AGENT_TYPE, METADATA_URI);
      await registry.connect(agent2).registerAgent("judge", "ipfs://agent2");
    });

    it("reflects correct job count", async () => {
      await registry.connect(owner).recordJobCompletion(agent1.address, MARKET_ID, true);
      await registry.connect(owner).recordJobCompletion(agent1.address, MARKET_ID, false);
      await registry.connect(owner).recordJobCompletion(agent2.address, MARKET_ID, true);

      const [, jobs] = await registry.getSystemStats();
      expect(jobs).to.equal(3n);
    });

    it("reflects correct dispute count", async () => {
      await registry.connect(owner).recordDisputeOutcome(MARKET_ID, true, 1_000_000n);
      await registry.connect(owner).recordDisputeOutcome(MARKET_ID, false, 0n);

      const [, , disputes, wins] = await registry.getSystemStats();
      expect(disputes).to.equal(2n);
      expect(wins).to.equal(1n);
    });

    it("reflects correct attestation count via incrementAttestations", async () => {
      await registry.connect(owner).incrementAttestations();
      await registry.connect(owner).incrementAttestations();

      const [attestations] = await registry.getSystemStats();
      expect(attestations).to.equal(2n);
    });
  });

  // =========================================================================
  // 7. recordDisputeOutcome
  // =========================================================================

  describe("recordDisputeOutcome", () => {
    it("increments totalDisputesTriggered on each call", async () => {
      await registry.connect(owner).recordDisputeOutcome(MARKET_ID, true,  500_000n);
      await registry.connect(owner).recordDisputeOutcome(MARKET_ID, false, 0n);

      const [, , disputes] = await registry.getSystemStats();
      expect(disputes).to.equal(2n);
    });

    it("increments totalDisputesWon only when won=true", async () => {
      await registry.connect(owner).recordDisputeOutcome(MARKET_ID, true,  500_000n);
      await registry.connect(owner).recordDisputeOutcome(MARKET_ID, false, 0n);

      const [, , , wins] = await registry.getSystemStats();
      expect(wins).to.equal(1n);
    });

    it("emits DisputeOutcome", async () => {
      await expect(
        registry.connect(owner).recordDisputeOutcome(MARKET_ID, true, 1_000_000n)
      )
        .to.emit(registry, "DisputeOutcome")
        .withArgs(MARKET_ID, true, 1_000_000n);
    });

    it("reverts for unauthorized caller", async () => {
      await expect(
        registry.connect(stranger).recordDisputeOutcome(MARKET_ID, true, 0n)
      ).to.be.revertedWith("Not authorized");
    });

    it("authorized non-owner can call recordDisputeOutcome", async () => {
      await registry.connect(owner).setAuthorized(agent1.address, true);
      await expect(
        registry.connect(agent1).recordDisputeOutcome(MARKET_ID, true, 100n)
      ).to.not.be.reverted;
    });
  });

  // =========================================================================
  // 8. setAuthorized
  // =========================================================================

  describe("setAuthorized", () => {
    it("owner can authorize a new caller", async () => {
      await registry.connect(owner).setAuthorized(agent1.address, true);
      expect(await registry.authorized(agent1.address)).to.be.true;
    });

    it("owner can revoke authorization", async () => {
      await registry.connect(owner).setAuthorized(agent1.address, true);
      await registry.connect(owner).setAuthorized(agent1.address, false);
      expect(await registry.authorized(agent1.address)).to.be.false;
    });

    it("emits AuthorizationChanged", async () => {
      await expect(registry.connect(owner).setAuthorized(agent1.address, true))
        .to.emit(registry, "AuthorizationChanged")
        .withArgs(agent1.address, true);
    });

    it("non-owner cannot call setAuthorized", async () => {
      await expect(
        registry.connect(stranger).setAuthorized(agent1.address, true)
      ).to.be.revertedWithCustomError(registry, "OwnableUnauthorizedAccount");
    });
  });

  // ===========================================================================
  // Internal helpers
  // ===========================================================================

  /**
   * Funds the registry address with USDC and impersonates it to approve
   * the BondManager.  Call this before any registerAgent() test.
   *
   * @param slots  How many MINIMUM_BOND-sized deposits to fund (default 1)
   */
  async function setupRegistryUsdcApproval(slots = 1) {
    const registryAddr  = await registry.getAddress();
    const bondMgrAddr   = await bondManager.getAddress();
    const totalNeeded   = MINIMUM_BOND * BigInt(slots);

    // Mint USDC to the registry contract
    await usdc.mint(registryAddr, totalNeeded);

    // Give the registry ETH for gas via hardhat_setBalance (avoids needing receive())
    await network.provider.send("hardhat_setBalance", [
      registryAddr,
      "0x" + ethers.parseEther("1").toString(16),
    ]);

    // Impersonate the registry to approve the BondManager
    await network.provider.send("hardhat_impersonateAccount", [registryAddr]);
    const registrySigner = await ethers.getSigner(registryAddr);
    await usdc.connect(registrySigner).approve(bondMgrAddr, totalNeeded);
    await network.provider.send("hardhat_stopImpersonatingAccount", [registryAddr]);
  }
});
