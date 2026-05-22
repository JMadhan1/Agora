// =============================================================================
// FILE: contracts/test/BondManager.test.ts
// =============================================================================
// Tests for BondManager.sol
//
// CONSTRAINT NOTE — hardcoded USDC_TOKEN:
//   BondManager.sol declares:
//     address public constant USDC_TOKEN = 0x3600000000000000000000000000000000000000;
//   This address is immutable and cannot be changed via a constructor parameter.
//
//   Strategy: use `hardhat_setCode` to deploy the MockERC20 bytecode at
//   0x3600000000000000000000000000000000000000 before each test.  This means
//   the local Hardhat node will route all BondManager USDC calls to our mock,
//   giving us full mint/approve control without modifying the production contract.
// =============================================================================

import { expect }                from "chai";
import { ethers, network }       from "hardhat";
import type { SignerWithAddress } from "@nomicfoundation/hardhat-ethers/signers";
import type { BondManager, MockERC20 } from "../typechain-types";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const USDC_HARDCODED = "0x3600000000000000000000000000000000000000";
const MINIMUM_BOND   = 10n * 1_000_000n; // 10 USDC, 6 decimals

// ---------------------------------------------------------------------------
// Helper: deploy MockERC20 bytecode at the hardcoded USDC address
// ---------------------------------------------------------------------------

async function deployMockAtUsdcAddress(): Promise<MockERC20> {
  const factory    = await ethers.getContractFactory("MockERC20");

  // Deploy a temporary instance purely to obtain the runtime bytecode.
  const tmp        = await factory.deploy("Mock USDC", "USDC", 6);
  await tmp.waitForDeployment();
  const deployedCode = await ethers.provider.getCode(await tmp.getAddress());

  // Overwrite code at the hardcoded address.
  // Note: hardhat_setCode replaces bytecode only — storage from previous
  // Hardhat snapshots persists.  Tests that care about a clean balance must
  // either use fresh signer addresses or explicitly call usdc.mint() for the
  // exact amount needed in that test.
  await network.provider.send("hardhat_setCode", [USDC_HARDCODED, deployedCode]);

  return factory.attach(USDC_HARDCODED) as unknown as MockERC20;
}

// ---------------------------------------------------------------------------
// Suite
// ---------------------------------------------------------------------------

describe("BondManager", () => {
  let bondManager: BondManager;
  let usdc:        MockERC20;
  let owner:       SignerWithAddress;
  let vault:       SignerWithAddress; // acts as the AttestationVault EOA in tests
  let agent:       SignerWithAddress;
  let agent2:      SignerWithAddress;
  let stranger:    SignerWithAddress;
  let winner:      SignerWithAddress;

  beforeEach(async () => {
    [owner, vault, agent, agent2, stranger, winner] = await ethers.getSigners();

    // Deploy MockERC20 at the hardcoded USDC address so BondManager uses it
    usdc = await deployMockAtUsdcAddress();

    // Deploy BondManager — vault parameter is the EOA we control in tests
    bondManager = await ethers.deployContract("BondManager", [
      owner.address,
      vault.address,
    ]) as unknown as BondManager;
  });

  // =========================================================================
  // 1. depositBond — happy path
  // =========================================================================

  describe("depositBond", () => {
    beforeEach(async () => {
      // Mint 100 USDC to agent and approve BondManager to spend MINIMUM_BOND
      await usdc.mint(agent.address, ethers.parseUnits("100", 6));
      await usdc.connect(agent).approve(await bondManager.getAddress(), MINIMUM_BOND);
    });

    it("transfers exactly MINIMUM_BOND (10 USDC) from agent to BondManager", async () => {
      const before = await usdc.balanceOf(agent.address);
      await bondManager.connect(agent).depositBond();
      const after = await usdc.balanceOf(agent.address);
      expect(before - after).to.equal(MINIMUM_BOND);
    });

    it("emits BondDeposited(agent, MINIMUM_BOND)", async () => {
      await expect(bondManager.connect(agent).depositBond())
        .to.emit(bondManager, "BondDeposited")
        .withArgs(agent.address, MINIMUM_BOND);
    });

    it("getBond returns 10e6 after deposit", async () => {
      await bondManager.connect(agent).depositBond();
      expect(await bondManager.getBond(agent.address)).to.equal(MINIMUM_BOND);
    });

    it("isBondSufficient returns true after deposit", async () => {
      await bondManager.connect(agent).depositBond();
      expect(await bondManager.isBondSufficient(agent.address)).to.be.true;
    });

    it("isBondSufficient returns false before deposit", async () => {
      expect(await bondManager.isBondSufficient(agent.address)).to.be.false;
    });

    it("isBondSufficient returns false when bond is below MINIMUM_BOND", async () => {
      // Mint a tiny amount and deposit a custom bond amount less than minimum
      // (depositBond always deposits exactly MINIMUM_BOND, so we verify the
      //  view function boundary by checking an address that never deposited)
      expect(await bondManager.isBondSufficient(stranger.address)).to.be.false;
    });

    it("successive deposits accumulate", async () => {
      await bondManager.connect(agent).depositBond();

      // Top up allowance and deposit again
      await usdc.connect(agent).approve(await bondManager.getAddress(), MINIMUM_BOND);
      await bondManager.connect(agent).depositBond();

      expect(await bondManager.getBond(agent.address)).to.equal(MINIMUM_BOND * 2n);
    });
  });

  // =========================================================================
  // 2. depositBond without approval — reverts
  // =========================================================================

  describe("depositBond without approval", () => {
    it("reverts when agent has no USDC allowance", async () => {
      await usdc.mint(agent.address, ethers.parseUnits("100", 6));
      // Deliberately skip approve() — MockERC20 reverts before returning false
      await expect(bondManager.connect(agent).depositBond())
        .to.be.revertedWith("ERC20: insufficient allowance");
    });

    it("reverts when agent has insufficient USDC balance", async () => {
      // Use stranger — guaranteed zero balance and zero allowance in every fresh run.
      // Grant allowance but no balance; MockERC20 reverts in _transfer.
      await usdc.connect(stranger).approve(await bondManager.getAddress(), MINIMUM_BOND);
      await expect(bondManager.connect(stranger).depositBond())
        .to.be.revertedWith("ERC20: insufficient balance");
    });
  });

  // =========================================================================
  // 3. slashBond — happy path
  // =========================================================================

  describe("slashBond", () => {
    beforeEach(async () => {
      await usdc.mint(agent.address, ethers.parseUnits("100", 6));
      await usdc.connect(agent).approve(await bondManager.getAddress(), MINIMUM_BOND);
      await bondManager.connect(agent).depositBond();
    });

    it("only vault can call slashBond", async () => {
      await expect(
        bondManager.connect(stranger).slashBond(agent.address, 1_000_000n, "bad call")
      ).to.be.revertedWith("Only vault");
    });

    it("reduces bond by slash amount", async () => {
      await bondManager.connect(vault).slashBond(agent.address, 3_000_000n, "wrong attestation");
      expect(await bondManager.getBond(agent.address)).to.equal(MINIMUM_BOND - 3_000_000n);
    });

    it("increments slashCount for agent", async () => {
      await bondManager.connect(vault).slashBond(agent.address, 1_000_000n, "test");
      expect(await bondManager.slashCount(agent.address)).to.equal(1n);
    });

    it("increments totalSlashed", async () => {
      await bondManager.connect(vault).slashBond(agent.address, 2_000_000n, "test");
      expect(await bondManager.totalSlashed()).to.equal(2_000_000n);
    });

    it("emits BondSlashed(agent, amount, reason)", async () => {
      await expect(
        bondManager.connect(vault).slashBond(agent.address, 5_000_000n, "manipulation")
      )
        .to.emit(bondManager, "BondSlashed")
        .withArgs(agent.address, 5_000_000n, "manipulation");
    });
  });

  // =========================================================================
  // 4. slashBond — amount exceeds bond (no underflow)
  // =========================================================================

  describe("slashBond — amount > bond", () => {
    beforeEach(async () => {
      await usdc.mint(agent.address, ethers.parseUnits("100", 6));
      await usdc.connect(agent).approve(await bondManager.getAddress(), MINIMUM_BOND);
      await bondManager.connect(agent).depositBond();
    });

    it("slashes only the available bond without underflow", async () => {
      // Request to slash 100 USDC but only 10 USDC is available
      const largeSlash = ethers.parseUnits("100", 6);
      await bondManager.connect(vault).slashBond(agent.address, largeSlash, "excess slash");

      // Bond should be 0, not negative
      expect(await bondManager.getBond(agent.address)).to.equal(0n);
    });

    it("emits BondSlashed with the capped (actual) amount", async () => {
      const largeSlash = ethers.parseUnits("100", 6);
      await expect(
        bondManager.connect(vault).slashBond(agent.address, largeSlash, "excess slash")
      )
        .to.emit(bondManager, "BondSlashed")
        .withArgs(agent.address, MINIMUM_BOND, "excess slash"); // only MINIMUM_BOND actually slashed
    });

    it("does nothing (no event) when agent has zero bond", async () => {
      // Slash entire bond first
      await bondManager.connect(vault).slashBond(agent.address, MINIMUM_BOND, "first");
      // Try to slash again — slashAmount becomes 0, early-return
      const tx = await bondManager.connect(vault).slashBond(agent.address, 1_000_000n, "second");
      const receipt = await tx.wait();
      // No BondSlashed event in logs
      const iface  = bondManager.interface;
      const slashed = receipt!.logs.filter(
        (log) => log.topics[0] === iface.getEvent("BondSlashed")!.topicHash
      );
      expect(slashed.length).to.equal(0);
    });
  });

  // =========================================================================
  // 5. slashBond from non-vault — reverts
  // =========================================================================

  describe("slashBond access control", () => {
    it("reverts with 'Only vault' for owner", async () => {
      await expect(
        bondManager.connect(owner).slashBond(agent.address, 1_000_000n, "owner")
      ).to.be.revertedWith("Only vault");
    });

    it("reverts with 'Only vault' for the agent itself", async () => {
      await expect(
        bondManager.connect(agent).slashBond(agent.address, 1_000_000n, "self")
      ).to.be.revertedWith("Only vault");
    });
  });

  // =========================================================================
  // 6. addDisputeReward + claimReward
  // =========================================================================

  describe("addDisputeReward and claimReward", () => {
    const REWARD = 3_000_000n; // 3 USDC

    beforeEach(async () => {
      // Mint USDC directly to BondManager so it can pay out rewards
      await usdc.mint(await bondManager.getAddress(), ethers.parseUnits("100", 6));
    });

    it("accumulates reward for winner via addDisputeReward", async () => {
      await bondManager.connect(vault).addDisputeReward(winner.address, REWARD);
      expect(await bondManager.getPendingReward(winner.address)).to.equal(REWARD);
    });

    it("only vault can call addDisputeReward", async () => {
      await expect(
        bondManager.connect(stranger).addDisputeReward(winner.address, REWARD)
      ).to.be.revertedWith("Only vault");
    });

    it("claimReward transfers USDC to winner", async () => {
      await bondManager.connect(vault).addDisputeReward(winner.address, REWARD);

      const before = await usdc.balanceOf(winner.address);
      await bondManager.connect(winner).claimReward();
      const after = await usdc.balanceOf(winner.address);

      expect(after - before).to.equal(REWARD);
    });

    it("emits RewardClaimed(winner, amount)", async () => {
      await bondManager.connect(vault).addDisputeReward(winner.address, REWARD);
      await expect(bondManager.connect(winner).claimReward())
        .to.emit(bondManager, "RewardClaimed")
        .withArgs(winner.address, REWARD);
    });

    it("zeroes pending reward after claim", async () => {
      await bondManager.connect(vault).addDisputeReward(winner.address, REWARD);
      await bondManager.connect(winner).claimReward();
      expect(await bondManager.getPendingReward(winner.address)).to.equal(0n);
    });

    it("reverts with 'No reward to claim' when nothing pending", async () => {
      await expect(bondManager.connect(winner).claimReward())
        .to.be.revertedWith("No reward to claim");
    });

    it("multiple addDisputeReward calls accumulate", async () => {
      await bondManager.connect(vault).addDisputeReward(winner.address, REWARD);
      await bondManager.connect(vault).addDisputeReward(winner.address, REWARD);
      expect(await bondManager.getPendingReward(winner.address)).to.equal(REWARD * 2n);
    });

    it("reverts addDisputeReward for zero address", async () => {
      await expect(
        bondManager.connect(vault).addDisputeReward(ethers.ZeroAddress, REWARD)
      ).to.be.revertedWith("Zero address");
    });

    it("reverts addDisputeReward for zero amount", async () => {
      await expect(
        bondManager.connect(vault).addDisputeReward(winner.address, 0n)
      ).to.be.revertedWith("Zero reward");
    });
  });

  // =========================================================================
  // 7. isBondSufficient — comprehensive boundary checks
  // =========================================================================

  describe("isBondSufficient boundaries", () => {
    it("returns false for a fresh address with no deposits", async () => {
      expect(await bondManager.isBondSufficient(stranger.address)).to.be.false;
    });

    it("returns true exactly at MINIMUM_BOND", async () => {
      await usdc.mint(agent.address, ethers.parseUnits("100", 6));
      await usdc.connect(agent).approve(await bondManager.getAddress(), MINIMUM_BOND);
      await bondManager.connect(agent).depositBond();
      expect(await bondManager.isBondSufficient(agent.address)).to.be.true;
    });

    it("returns false when bond is slashed below MINIMUM_BOND", async () => {
      await usdc.mint(agent.address, ethers.parseUnits("100", 6));
      await usdc.connect(agent).approve(await bondManager.getAddress(), MINIMUM_BOND);
      await bondManager.connect(agent).depositBond();

      // Slash 1 wei above zero remaining (slash all but 1 unit)
      await bondManager.connect(vault).slashBond(agent.address, MINIMUM_BOND - 1n, "partial");
      // Bond is now 1 (< MINIMUM_BOND)
      expect(await bondManager.isBondSufficient(agent.address)).to.be.false;
    });
  });

  // =========================================================================
  // 8. setVault — owner can update vault address
  // =========================================================================

  describe("setVault", () => {
    it("owner can update vault address", async () => {
      await bondManager.connect(owner).setVault(agent.address);
      expect(await bondManager.attestationVault()).to.equal(agent.address);
    });

    it("non-owner cannot update vault address", async () => {
      await expect(bondManager.connect(stranger).setVault(agent.address))
        .to.be.revertedWithCustomError(bondManager, "OwnableUnauthorizedAccount");
    });

    it("reverts for zero vault address", async () => {
      await expect(bondManager.connect(owner).setVault(ethers.ZeroAddress))
        .to.be.revertedWith("Zero address");
    });

    it("emits VaultUpdated event", async () => {
      await expect(bondManager.connect(owner).setVault(agent.address))
        .to.emit(bondManager, "VaultUpdated")
        .withArgs(agent.address);
    });
  });
});
