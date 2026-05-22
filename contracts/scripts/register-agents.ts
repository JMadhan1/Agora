import { ethers } from "hardhat";
import fs from "fs";
import path from "path";
import axios from "axios";

// ─────────────────────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────────────────────

const PROJECT_ROOT = path.resolve(__dirname, "..", "..");
const ADDRESSES_FILE = path.join(PROJECT_ROOT, "deployed-addresses.json");
const AGENT_WALLETS_FILE = path.join(PROJECT_ROOT, "agents", ".agent-wallets.json");

const ARCSCAN_BASE = "https://testnet.arcscan.app/tx";

const IRYS_UPLOAD_URL = "https://uploader.irys.xyz/upload";

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface DeployedAddresses {
  attestationVault: string;
  bondManager: string;
  sentinelRegistry: string;
  deployedAt: string;
  chainId: number;
  deployer: string;
  blockNumber: number;
}

interface AgentWalletEntry {
  address: string;
  walletId: string;
  erc8004MetadataUri?: string;
}

interface AgentWallets {
  scout: AgentWalletEntry;
  judge: AgentWalletEntry;
  watchdog: AgentWalletEntry;
}

interface AgentMetadata {
  name: string;
  description: string;
  agent_type: string;
  capabilities: string[];
  version: string;
  oracle_sentinel_version: string;
  network: string;
  builder: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// Agent Metadata Definitions
// ─────────────────────────────────────────────────────────────────────────────

const AGENT_METADATA: Record<string, AgentMetadata> = {
  scout: {
    name: "Oracle Sentinel Scout Agent",
    description:
      "Continuously monitors Polymarket prediction markets for breaking news and on-chain events. " +
      "Queries news APIs, social sentiment, and blockchain data to surface early signals before " +
      "market prices reflect new information. Feeds verified evidence to the Judge Agent.",
    agent_type: "scout",
    capabilities: [
      "news_analysis",
      "onchain_verification",
      "wayback_search",
      "market_data",
      "social_sentiment",
    ],
    version: "1.0.0",
    oracle_sentinel_version: "1.0.0",
    network: "arc-testnet",
    builder: "Oracle Sentinel — Agora Hackathon 2026",
  },
  judge: {
    name: "Oracle Sentinel Judge Agent",
    description:
      "Receives evidence bundles from the Scout Agent and performs deep multi-source reasoning " +
      "to produce a calibrated confidence score (0–100) for each Polymarket market. Commits " +
      "SHA-256 reasoning trace hashes to AttestationVault and stores full traces on IPFS.",
    agent_type: "judge",
    capabilities: [
      "multi_source_reasoning",
      "confidence_calibration",
      "ipfs_storage",
      "attestation_commit",
      "llm_inference",
    ],
    version: "1.0.0",
    oracle_sentinel_version: "1.0.0",
    network: "arc-testnet",
    builder: "Oracle Sentinel — Agora Hackathon 2026",
  },
  watchdog: {
    name: "Oracle Sentinel Watchdog Agent",
    description:
      "Monitors UMA oracle resolutions and compares final verdicts against Judge Agent attestations. " +
      "If deviation exceeds 40%, the Watchdog triggers a UMA dispute and flags the attestation as " +
      "disputed on-chain. Protects market integrity against manipulation and bad data.",
    agent_type: "watchdog",
    capabilities: [
      "uma_monitoring",
      "dispute_trigger",
      "deviation_analysis",
      "bond_management",
      "manipulation_detection",
    ],
    version: "1.0.0",
    oracle_sentinel_version: "1.0.0",
    network: "arc-testnet",
    builder: "Oracle Sentinel — Agora Hackathon 2026",
  },
};

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

/** Upload JSON metadata to Irys and return the content URI. */
async function uploadToIrys(metadata: AgentMetadata): Promise<string> {
  const data = JSON.stringify(metadata);
  const response = await axios.post(IRYS_UPLOAD_URL, data, {
    headers: { "Content-Type": "application/json" },
    timeout: 15_000,
  });

  const id: string | undefined =
    response.data?.id ?? response.data?.receipt?.id ?? response.data?.txId;

  if (!id) {
    throw new Error(
      `Irys upload succeeded but no transaction ID in response: ${JSON.stringify(response.data)}`
    );
  }

  return `https://gateway.irys.xyz/${id}`;
}

/** Deterministic fallback IPFS CID for when Irys is unavailable. */
function fallbackCid(agentType: string): string {
  // These are well-formed but placeholder CIDv1 base32 strings.
  const cids: Record<string, string> = {
    scout:
      "bafkreihdwdcefgh4dqkjv67uzcmw37lor52mthe53lnagxa62aw36tjihm",
    judge:
      "bafkreiabo3kpz6vf2u2f7i3s2gzvotq5g7yqpjtdv3ij2xbkzq4yl7cdy",
    watchdog:
      "bafkreiebcdefghijklmnopqrstuvwxyz234567abcdefghijklmnopqrstu",
  };
  return `ipfs://${cids[agentType] ?? "bafkreihdwdcefgh4dqkjv67uzcmw37lor52mthe53lnagxa62aw36tjihm"}`;
}

/** Print a horizontal separator. */
function hr(char = "─", width = 68): string {
  return char.repeat(width);
}

// ─────────────────────────────────────────────────────────────────────────────
// Main
// ─────────────────────────────────────────────────────────────────────────────

async function main(): Promise<void> {
  console.log("\n" + hr("═"));
  console.log("  Oracle Sentinel — Agent Registration Script");
  console.log("  Network : Arc Testnet (chainId 5042002)");
  console.log(hr("═") + "\n");

  // ── Load deployed addresses ──────────────────────────────────────────────────
  if (!fs.existsSync(ADDRESSES_FILE)) {
    throw new Error(
      `deployed-addresses.json not found at ${ADDRESSES_FILE}.\n` +
        "Run `npx hardhat run scripts/deploy.ts --network arcTestnet` first."
    );
  }
  const addresses: DeployedAddresses = JSON.parse(
    fs.readFileSync(ADDRESSES_FILE, "utf8")
  );
  console.log(`Loaded addresses from ${ADDRESSES_FILE}`);
  console.log(`  AttestationVault  : ${addresses.attestationVault}`);
  console.log(`  BondManager       : ${addresses.bondManager}`);
  console.log(`  SentinelRegistry  : ${addresses.sentinelRegistry}`);

  // ── Load agent wallets ────────────────────────────────────────────────────────
  if (!fs.existsSync(AGENT_WALLETS_FILE)) {
    throw new Error(
      `Agent wallets file not found at ${AGENT_WALLETS_FILE}.\n` +
        "Run the wallet generation step first (see README)."
    );
  }
  const agentWallets: AgentWallets = JSON.parse(
    fs.readFileSync(AGENT_WALLETS_FILE, "utf8")
  );
  console.log(`\nLoaded agent wallets from ${AGENT_WALLETS_FILE}`);
  console.log(`  Scout    : ${agentWallets.scout.address}`);
  console.log(`  Judge    : ${agentWallets.judge.address}`);
  console.log(`  Watchdog : ${agentWallets.watchdog.address}`);

  // ── Signer & contracts ────────────────────────────────────────────────────────
  const [deployer] = await ethers.getSigners();
  console.log(`\nDeployer : ${deployer.address}`);

  const vault = await ethers.getContractAt(
    "AttestationVault",
    addresses.attestationVault,
    deployer
  );

  // ── Bond requirement notice ───────────────────────────────────────────────────
  console.log("\n" + hr());
  console.log(
    "⚠️  To register agents, each agent wallet must approve 10 USDC to BondManager at " +
      addresses.bondManager +
      " and then call registerAgent()"
  );
  console.log(
    "   This script instead calls vault.addAgent() from the deployer so agents can\n" +
      "   commit attestations immediately without posting a bond on-chain.\n" +
      "   Use `registerAgent()` from each agent's own wallet for full bond participation."
  );
  console.log(hr());

  // ── Process each agent ────────────────────────────────────────────────────────
  const agentEntries: [keyof AgentWallets, AgentWalletEntry][] = [
    ["scout",    agentWallets.scout],
    ["judge",    agentWallets.judge],
    ["watchdog", agentWallets.watchdog],
  ];

  for (const [agentType, agentEntry] of agentEntries) {
    console.log(`\n${hr()}`);
    console.log(`Processing ${agentType.toUpperCase()} agent (${agentEntry.address})…`);

    const metadata = AGENT_METADATA[agentType];

    // ── Upload ERC-8004 metadata to Irys ────────────────────────────────────────
    let metadataUri: string;
    try {
      console.log(`  Uploading ERC-8004 metadata to Irys…`);
      metadataUri = await uploadToIrys(metadata);
      console.log(`  ✅ Irys upload successful: ${metadataUri}`);
    } catch (irysErr) {
      const msg = (irysErr as Error).message;
      console.warn(`  ⚠️  Irys upload failed (${msg}) — using placeholder IPFS CID`);
      metadataUri = fallbackCid(agentType);
      console.log(`  Fallback metadata URI: ${metadataUri}`);
    }

    // ── vault.addAgent() from deployer ───────────────────────────────────────────
    try {
      console.log(`  Calling vault.addAgent(${agentEntry.address})…`);
      const tx = await (vault as any).addAgent(agentEntry.address);
      const receipt = await tx.wait();
      const txHash: string = receipt?.hash ?? tx.hash;
      console.log(`  ✅ vault.addAgent confirmed`);
      console.log(`     ArcScan: ${ARCSCAN_BASE}/${txHash}`);
    } catch (err) {
      const msg = (err as Error).message;
      // "Already authorized" is fine — agent wallet may have been added during deploy
      if (msg.toLowerCase().includes("already") || msg.toLowerCase().includes("authorized")) {
        console.log(`  ℹ️  Agent already authorized in vault — skipping`);
      } else {
        console.error(`  ✗ vault.addAgent failed: ${msg}`);
      }
    }

    // ── Persist metadata URI back to .agent-wallets.json ────────────────────────
    agentWallets[agentType].erc8004MetadataUri = metadataUri;
    console.log(`  ERC-8004 URI saved for ${agentType}`);
  }

  // ── Write updated .agent-wallets.json ─────────────────────────────────────────
  fs.writeFileSync(AGENT_WALLETS_FILE, JSON.stringify(agentWallets, null, 2), "utf8");
  console.log(`\n📄 Updated agent wallets written → ${AGENT_WALLETS_FILE}`);

  // ── Summary ───────────────────────────────────────────────────────────────────
  console.log("\n" + hr("═"));
  console.log("  Registration Summary");
  console.log(hr("═"));
  for (const [agentType, agentEntry] of agentEntries) {
    console.log(`  ${agentType.padEnd(10)} : ${agentEntry.address}`);
    console.log(`  ${"".padEnd(10)}   URI: ${agentWallets[agentType].erc8004MetadataUri}`);
  }
  console.log(hr("═"));
  console.log("\n  Next steps:");
  console.log("  1. Fund each agent wallet with testnet ETH for gas");
  console.log(`  2. Fund each agent wallet with ≥10 USDC (${addresses.bondManager})`);
  console.log("  3. From each agent wallet, approve 10 USDC to BondManager then call:");
  console.log(`     OracleSentinelRegistry.registerAgent(agentType, metadataUri)`);
  console.log(hr("═") + "\n");
}

// ─────────────────────────────────────────────────────────────────────────────
// Entry point
// ─────────────────────────────────────────────────────────────────────────────

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
