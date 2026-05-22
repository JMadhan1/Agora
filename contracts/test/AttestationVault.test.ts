// =============================================================================
// FILE: contracts/test/AttestationVault.test.ts
// =============================================================================
// Tests for AttestationVault.sol
// Runs on the local Hardhat network (chainId 31337).
// No external dependencies — only MockERC20 is needed here for consistency,
// although AttestationVault itself has no token dependency.
// =============================================================================

import { expect }           from "chai";
import { ethers }           from "hardhat";
import { anyValue }         from "@nomicfoundation/hardhat-chai-matchers/withArgs";
import type { SignerWithAddress } from "@nomicfoundation/hardhat-ethers/signers";
import type { AttestationVault } from "../typechain-types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const MARKET_ID = "0x1234abcd";
const IPFS_CID  = "QmXyzAbcDeFgHiJkLmNoPqRsTuVwXyZ1234567890abcdef";

function makeHash(seed: number): string {
  return ethers.keccak256(ethers.toUtf8Bytes(`trace-seed-${seed}`));
}

// ---------------------------------------------------------------------------
// Suite
// ---------------------------------------------------------------------------

describe("AttestationVault", () => {
  let vault:   AttestationVault;
  let owner:   SignerWithAddress;
  let agent:   SignerWithAddress;
  let agent2:  SignerWithAddress;
  let stranger: SignerWithAddress;

  beforeEach(async () => {
    [owner, agent, agent2, stranger] = await ethers.getSigners();

    vault = await ethers.deployContract("AttestationVault", [owner.address]) as unknown as AttestationVault;
  });

  // =========================================================================
  // 1. Deployment
  // =========================================================================

  describe("Deployment", () => {
    it("sets the initialOwner correctly", async () => {
      expect(await vault.owner()).to.equal(owner.address);
    });

    it("starts with totalAttestations = 0", async () => {
      expect(await vault.totalAttestations()).to.equal(0n);
    });

    it("starts with the deployer not authorized as agent", async () => {
      expect(await vault.isAuthorized(owner.address)).to.be.false;
    });
  });

  // =========================================================================
  // 2. addAgent
  // =========================================================================

  describe("addAgent", () => {
    it("owner can add an agent", async () => {
      await vault.connect(owner).addAgent(agent.address);
      expect(await vault.isAuthorized(agent.address)).to.be.true;
    });

    it("emits AgentAuthorizationChanged(agent, true)", async () => {
      await expect(vault.connect(owner).addAgent(agent.address))
        .to.emit(vault, "AgentAuthorizationChanged")
        .withArgs(agent.address, true);
    });

    it("reverts when called by a non-owner", async () => {
      await expect(vault.connect(stranger).addAgent(agent.address))
        .to.be.revertedWithCustomError(vault, "OwnableUnauthorizedAccount")
        .withArgs(stranger.address);
    });

    it("reverts for zero address", async () => {
      await expect(vault.connect(owner).addAgent(ethers.ZeroAddress))
        .to.be.revertedWith("Zero address");
    });

    it("authorizedAgents mapping is true after addAgent", async () => {
      await vault.connect(owner).addAgent(agent.address);
      expect(await vault.authorizedAgents(agent.address)).to.be.true;
    });
  });

  // =========================================================================
  // 3. removeAgent
  // =========================================================================

  describe("removeAgent", () => {
    beforeEach(async () => {
      await vault.connect(owner).addAgent(agent.address);
    });

    it("owner can remove an agent", async () => {
      await vault.connect(owner).removeAgent(agent.address);
      expect(await vault.isAuthorized(agent.address)).to.be.false;
    });

    it("emits AgentAuthorizationChanged(agent, false)", async () => {
      await expect(vault.connect(owner).removeAgent(agent.address))
        .to.emit(vault, "AgentAuthorizationChanged")
        .withArgs(agent.address, false);
    });

    it("subsequent commitAttestation from removed agent reverts", async () => {
      await vault.connect(owner).removeAgent(agent.address);
      await expect(
        vault.connect(agent).commitAttestation(
          MARKET_ID, makeHash(1), IPFS_CID, 80
        )
      ).to.be.revertedWith("Not authorized agent");
    });

    it("non-owner cannot remove an agent", async () => {
      await expect(vault.connect(stranger).removeAgent(agent.address))
        .to.be.revertedWithCustomError(vault, "OwnableUnauthorizedAccount");
    });
  });

  // =========================================================================
  // 4. commitAttestation
  // =========================================================================

  describe("commitAttestation", () => {
    const hash1 = makeHash(1);

    beforeEach(async () => {
      await vault.connect(owner).addAgent(agent.address);
    });

    // -----------------------------------------------------------------------
    // Happy path
    // -----------------------------------------------------------------------

    it("emits AttestationCommitted with correct args", async () => {
      const tx = await vault
        .connect(agent)
        .commitAttestation(MARKET_ID, hash1, IPFS_CID, 85);

      const receipt = await tx.wait();
      const block   = await ethers.provider.getBlock(receipt!.blockNumber);

      // marketId is an indexed string — its topic is keccak256(marketId).
      // agent is an indexed address — matched directly.
      // Non-indexed args (traceHash, ipfsCid, confidence, timestamp) are ABI-decoded.
      await expect(tx)
        .to.emit(vault, "AttestationCommitted")
        .withArgs(
          anyValue,        // indexed string: marketId (topic hash, not the value itself)
          hash1,           // non-indexed bytes32
          IPFS_CID,        // non-indexed string
          85,              // non-indexed uint8
          agent.address,   // indexed address
          block!.timestamp // non-indexed uint256
        );
    });

    it("increments totalAttestations", async () => {
      await vault.connect(agent).commitAttestation(MARKET_ID, hash1, IPFS_CID, 70);
      expect(await vault.totalAttestations()).to.equal(1n);
    });

    it("hashExists returns true after commit", async () => {
      await vault.connect(agent).commitAttestation(MARKET_ID, hash1, IPFS_CID, 70);
      expect(await vault.hashExists(hash1)).to.be.true;
    });

    it("getAttestationCount returns 1 after one commit", async () => {
      await vault.connect(agent).commitAttestation(MARKET_ID, hash1, IPFS_CID, 70);
      expect(await vault.getAttestationCount(MARKET_ID)).to.equal(1n);
    });

    it("stored attestation fields match the input", async () => {
      await vault.connect(agent).commitAttestation(MARKET_ID, hash1, IPFS_CID, 90);
      const attestation = await vault.getLatestAttestation(MARKET_ID);
      expect(attestation.traceHash).to.equal(hash1);
      expect(attestation.ipfsCid).to.equal(IPFS_CID);
      expect(attestation.marketId).to.equal(MARKET_ID);
      expect(attestation.confidence).to.equal(90);
      expect(attestation.agentAddress).to.equal(agent.address);
      expect(attestation.disputed).to.be.false;
    });

    // -----------------------------------------------------------------------
    // Revert: duplicate hash
    // -----------------------------------------------------------------------

    it("reverts with 'Hash already committed' on duplicate hash", async () => {
      await vault.connect(agent).commitAttestation(MARKET_ID, hash1, IPFS_CID, 60);
      await expect(
        vault.connect(agent).commitAttestation(MARKET_ID, hash1, IPFS_CID, 60)
      ).to.be.revertedWith("Hash already committed");
    });

    // -----------------------------------------------------------------------
    // Revert: unauthorized caller
    // -----------------------------------------------------------------------

    it("reverts with 'Not authorized agent' for non-agent caller", async () => {
      await expect(
        vault.connect(stranger).commitAttestation(MARKET_ID, hash1, IPFS_CID, 60)
      ).to.be.revertedWith("Not authorized agent");
    });

    // -----------------------------------------------------------------------
    // Revert: zero hash
    // -----------------------------------------------------------------------

    it("reverts with 'Zero hash' for bytes32(0) traceHash", async () => {
      const zeroHash = ethers.ZeroHash; // 0x0000...0000
      await expect(
        vault.connect(agent).commitAttestation(MARKET_ID, zeroHash, IPFS_CID, 60)
      ).to.be.revertedWith("Zero hash");
    });

    // -----------------------------------------------------------------------
    // Revert: confidence out of range
    // -----------------------------------------------------------------------

    it("reverts with 'Confidence > 100' when confidence is 101", async () => {
      await expect(
        vault.connect(agent).commitAttestation(MARKET_ID, hash1, IPFS_CID, 101)
      ).to.be.revertedWith("Confidence > 100");
    });

    it("accepts confidence == 100 (boundary)", async () => {
      await expect(
        vault.connect(agent).commitAttestation(MARKET_ID, hash1, IPFS_CID, 100)
      ).to.not.be.reverted;
    });

    it("accepts confidence == 0 (boundary)", async () => {
      await expect(
        vault.connect(agent).commitAttestation(MARKET_ID, hash1, IPFS_CID, 0)
      ).to.not.be.reverted;
    });

    // -----------------------------------------------------------------------
    // Revert: empty marketId
    // -----------------------------------------------------------------------

    it("reverts with 'Empty marketId' for empty string", async () => {
      await expect(
        vault.connect(agent).commitAttestation("", hash1, IPFS_CID, 50)
      ).to.be.revertedWith("Empty marketId");
    });
  });

  // =========================================================================
  // 5. getAttestations — full array after multiple commits
  // =========================================================================

  describe("getAttestations", () => {
    beforeEach(async () => {
      await vault.connect(owner).addAgent(agent.address);
    });

    it("returns all attestations in chronological order", async () => {
      for (let i = 1; i <= 3; i++) {
        await vault
          .connect(agent)
          .commitAttestation(MARKET_ID, makeHash(i), `${IPFS_CID}-${i}`, i * 20);
      }

      const attestations = await vault.getAttestations(MARKET_ID);
      expect(attestations.length).to.equal(3);
      expect(attestations[0].traceHash).to.equal(makeHash(1));
      expect(attestations[1].traceHash).to.equal(makeHash(2));
      expect(attestations[2].traceHash).to.equal(makeHash(3));
    });

    it("returns empty array for a market with no attestations", async () => {
      const attestations = await vault.getAttestations("unknown-market");
      expect(attestations.length).to.equal(0);
    });

    it("attestations from different markets are isolated", async () => {
      await vault.connect(owner).addAgent(agent2.address);
      await vault.connect(agent).commitAttestation(MARKET_ID, makeHash(10), IPFS_CID, 50);
      await vault.connect(agent2).commitAttestation("other-market", makeHash(11), IPFS_CID, 50);

      expect((await vault.getAttestations(MARKET_ID)).length).to.equal(1);
      expect((await vault.getAttestations("other-market")).length).to.equal(1);
    });
  });

  // =========================================================================
  // 6. getLatestAttestation
  // =========================================================================

  describe("getLatestAttestation", () => {
    beforeEach(async () => {
      await vault.connect(owner).addAgent(agent.address);
    });

    it("returns the most recently committed attestation", async () => {
      await vault.connect(agent).commitAttestation(MARKET_ID, makeHash(1), IPFS_CID, 40);
      await vault.connect(agent).commitAttestation(MARKET_ID, makeHash(2), IPFS_CID, 90);

      const latest = await vault.getLatestAttestation(MARKET_ID);
      expect(latest.traceHash).to.equal(makeHash(2));
      expect(latest.confidence).to.equal(90);
    });

    it("reverts with 'No attestations for market' when market is empty", async () => {
      await expect(vault.getLatestAttestation("empty-market"))
        .to.be.revertedWith("No attestations for market");
    });
  });

  // =========================================================================
  // 7. flagDispute
  // =========================================================================

  describe("flagDispute", () => {
    const hash1 = makeHash(99);

    beforeEach(async () => {
      await vault.connect(owner).addAgent(agent.address);
      await vault.connect(agent).commitAttestation(MARKET_ID, hash1, IPFS_CID, 70);
    });

    it("sets disputed=true on the target attestation", async () => {
      await vault.connect(agent).flagDispute(MARKET_ID, hash1, "Manipulation detected");
      const attestation = await vault.getLatestAttestation(MARKET_ID);
      expect(attestation.disputed).to.be.true;
    });

    it("emits DisputeFlagged with correct args", async () => {
      // marketId and flaggedBy are indexed; reason and traceHash are not.
      await expect(
        vault.connect(agent).flagDispute(MARKET_ID, hash1, "Manipulation detected")
      )
        .to.emit(vault, "DisputeFlagged")
        .withArgs(
          anyValue,               // indexed string: marketId
          hash1,                  // non-indexed bytes32
          "Manipulation detected",// non-indexed string
          agent.address           // indexed address
        );
    });

    it("reverts with 'Hash not found' for an unregistered hash", async () => {
      const unknownHash = makeHash(888);
      await expect(
        vault.connect(agent).flagDispute(MARKET_ID, unknownHash, "reason")
      ).to.be.revertedWith("Hash not found");
    });

    it("reverts with 'Attestation not found for market' when hash exists but belongs to another market", async () => {
      // hash1 was committed under MARKET_ID — flagging under a different market should fail
      await expect(
        vault.connect(agent).flagDispute("other-market", hash1, "wrong market")
      ).to.be.revertedWith("Attestation not found for market");
    });

    it("reverts with 'Not authorized agent' for unauthorized caller", async () => {
      await expect(
        vault.connect(stranger).flagDispute(MARKET_ID, hash1, "hack attempt")
      ).to.be.revertedWith("Not authorized agent");
    });

    it("reverts with 'Empty reason' for empty reason string", async () => {
      await expect(
        vault.connect(agent).flagDispute(MARKET_ID, hash1, "")
      ).to.be.revertedWith("Empty reason");
    });
  });
});
