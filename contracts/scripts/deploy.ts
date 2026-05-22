import { ethers } from "hardhat";
import fs from "fs";
import path from "path";

// ─────────────────────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────────────────────

const USDC_ADDRESS = "0x3600000000000000000000000000000000000000";
const USDC_DECIMALS = 6;
const WARN_BELOW_USDC = 1_000_000n; // 1 USDC in 6-decimal units

const ARCSCAN_BASE = "https://testnet.arcscan.app/address";

const PROJECT_ROOT = path.resolve(__dirname, "..", "..");
const ADDRESSES_FILE = path.join(PROJECT_ROOT, "deployed-addresses.json");
const ENV_FILE = path.join(PROJECT_ROOT, ".env");

// Minimal ERC-20 ABI for balance check
const ERC20_ABI = [
  "function balanceOf(address owner) view returns (uint256)",
];

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

/** Replace (or append) a KEY=VALUE line in an .env file string. */
function patchEnvLine(content: string, key: string, value: string): string {
  const regex = new RegExp(`^${key}=.*$`, "m");
  const newLine = `${key}=${value}`;
  if (regex.test(content)) {
    return content.replace(regex, newLine);
  }
  // Append if key not present
  return content.trimEnd() + `\n${newLine}\n`;
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
  console.log("  Oracle Sentinel — Deployment Script");
  console.log("  Network : Arc Testnet (chainId 5042002)");
  console.log(hr("═") + "\n");

  // ── Signer ──────────────────────────────────────────────────────────────────
  const [deployer] = await ethers.getSigners();
  console.log(`Deployer : ${deployer.address}`);

  // ── USDC Balance Check ───────────────────────────────────────────────────────
  try {
    const usdc = new ethers.Contract(USDC_ADDRESS, ERC20_ABI, deployer);
    const usdcBalance: bigint = await usdc.balanceOf(deployer.address);
    const usdcFormatted = (Number(usdcBalance) / 10 ** USDC_DECIMALS).toFixed(6);
    console.log(`USDC bal : ${usdcFormatted} USDC`);
    if (usdcBalance < WARN_BELOW_USDC) {
      console.warn(
        `\n⚠️  WARNING: Deployer USDC balance is below 1 USDC (${usdcFormatted} USDC).` +
          "\n   Agent registration bonds (10 USDC each) will fail without sufficient USDC." +
          "\n   Top up at https://faucet.testnet.arc-node.thecanteenapp.com\n"
      );
    }
  } catch (err) {
    console.warn("⚠️  Could not fetch USDC balance:", (err as Error).message);
  }

  console.log("\n" + hr());

  // ── 1. Deploy AttestationVault ───────────────────────────────────────────────
  console.log("\n[1/3] Deploying AttestationVault…");
  const VaultFactory = await ethers.getContractFactory("AttestationVault");
  const vault = await VaultFactory.deploy(deployer.address);
  await vault.waitForDeployment();
  const vaultAddress = await vault.getAddress();
  const vaultTx = vault.deploymentTransaction();
  console.log(`✅ AttestationVault deployed: ${ARCSCAN_BASE}/${vaultAddress}`);
  console.log(`   Tx hash : ${vaultTx?.hash ?? "unknown"}`);

  // ── 2. Deploy BondManager ────────────────────────────────────────────────────
  console.log("\n[2/3] Deploying BondManager…");
  const BondFactory = await ethers.getContractFactory("BondManager");
  const bondManager = await BondFactory.deploy(deployer.address, vaultAddress);
  await bondManager.waitForDeployment();
  const bondManagerAddress = await bondManager.getAddress();
  const bondTx = bondManager.deploymentTransaction();
  console.log(`✅ BondManager deployed: ${ARCSCAN_BASE}/${bondManagerAddress}`);
  console.log(`   Tx hash : ${bondTx?.hash ?? "unknown"}`);

  // ── 3. Deploy DisputeInsurance ───────────────────────────────────────────────
  console.log("\n[3/4] Deploying DisputeInsurance…");
  const watchdogWallet = process.env.WATCHDOG_WALLET || deployer.address;
  const InsuranceFactory = await ethers.getContractFactory("DisputeInsurance");
  const insurance = await InsuranceFactory.deploy(deployer.address, USDC_ADDRESS, watchdogWallet);
  await insurance.waitForDeployment();
  const insuranceAddress = await insurance.getAddress();
  const insuranceTx = insurance.deploymentTransaction();
  console.log(`✅ DisputeInsurance deployed: ${ARCSCAN_BASE}/${insuranceAddress}`);
  console.log(`   Tx hash : ${insuranceTx?.hash ?? "unknown"}`);
  console.log(`   Watchdog: ${watchdogWallet}`);

  // ── 4. Deploy OracleSentinelRegistry ─────────────────────────────────────────
  console.log("\n[4/4] Deploying OracleSentinelRegistry…");
  const RegistryFactory = await ethers.getContractFactory("OracleSentinelRegistry");
  const registry = await RegistryFactory.deploy(
    deployer.address,
    vaultAddress,
    bondManagerAddress
  );
  await registry.waitForDeployment();
  const registryAddress = await registry.getAddress();
  const registryTx = registry.deploymentTransaction();
  console.log(`✅ OracleSentinelRegistry deployed: ${ARCSCAN_BASE}/${registryAddress}`);
  console.log(`   Tx hash : ${registryTx?.hash ?? "unknown"}`);

  // ── Agent Wallet Authorization ────────────────────────────────────────────────
  console.log("\n" + hr());
  console.log("\nAuthorizing agent wallets…");

  const agentWallets: { name: string; address: string | undefined }[] = [
    { name: "SCOUT_WALLET",    address: process.env.SCOUT_WALLET    || undefined },
    { name: "JUDGE_WALLET",    address: process.env.JUDGE_WALLET    || undefined },
    { name: "WATCHDOG_WALLET", address: process.env.WATCHDOG_WALLET || undefined },
  ];

  let anyWallet = false;
  for (const { name, address: walletAddr } of agentWallets) {
    if (!walletAddr || walletAddr.trim() === "") {
      console.log(`   ${name} not set — skipping`);
      continue;
    }
    anyWallet = true;

    // addAgent on AttestationVault
    try {
      const addTx = await (vault as any).addAgent(walletAddr);
      await addTx.wait();
      console.log(`   vault.addAgent(${walletAddr})  ✓  (${name})`);
    } catch (err) {
      console.warn(`   vault.addAgent failed for ${name}: ${(err as Error).message}`);
    }

    // setAuthorized on OracleSentinelRegistry
    try {
      const authTx = await (registry as any).setAuthorized(walletAddr, true);
      await authTx.wait();
      console.log(`   registry.setAuthorized(${walletAddr}, true)  ✓  (${name})`);
    } catch (err) {
      console.warn(`   registry.setAuthorized failed for ${name}: ${(err as Error).message}`);
    }
  }

  if (!anyWallet) {
    console.log("   No agent wallet env vars set — authorization step skipped.");
    console.log("   Set SCOUT_WALLET, JUDGE_WALLET, WATCHDOG_WALLET and re-run to authorize.");
  }

  // ── Retrieve block number ─────────────────────────────────────────────────────
  const provider = deployer.provider!;
  const blockNumber = await provider.getBlockNumber();
  const network = await provider.getNetwork();
  const chainId = Number(network.chainId);

  // ── Write deployed-addresses.json ────────────────────────────────────────────
  const deployedAt = new Date().toISOString();
  const addressesPayload = {
    attestationVault: vaultAddress,
    bondManager: bondManagerAddress,
    sentinelRegistry: registryAddress,
    disputeInsurance: insuranceAddress,
    deployedAt,
    chainId,
    deployer: deployer.address,
    blockNumber,
  };

  fs.writeFileSync(ADDRESSES_FILE, JSON.stringify(addressesPayload, null, 2), "utf8");
  console.log(`\n📄 Addresses written → ${ADDRESSES_FILE}`);

  // ── Patch .env ────────────────────────────────────────────────────────────────
  if (fs.existsSync(ENV_FILE)) {
    let envContent = fs.readFileSync(ENV_FILE, "utf8");
    envContent = patchEnvLine(envContent, "ATTESTATION_VAULT_ADDRESS", vaultAddress);
    envContent = patchEnvLine(envContent, "BOND_MANAGER_ADDRESS", bondManagerAddress);
    envContent = patchEnvLine(envContent, "DISPUTE_INSURANCE_ADDRESS", insuranceAddress);
    envContent = patchEnvLine(envContent, "SENTINEL_REGISTRY_ADDRESS", registryAddress);
    fs.writeFileSync(ENV_FILE, envContent, "utf8");
    console.log(`📝 .env updated → ${ENV_FILE}`);
  } else {
    console.warn(`⚠️  .env not found at ${ENV_FILE} — skipping auto-patch.`);
    console.log("   Add these lines manually:");
    console.log(`   ATTESTATION_VAULT_ADDRESS=${vaultAddress}`);
    console.log(`   BOND_MANAGER_ADDRESS=${bondManagerAddress}`);
    console.log(`   SENTINEL_REGISTRY_ADDRESS=${registryAddress}`);
  }

  // ── Summary Table ─────────────────────────────────────────────────────────────
  console.log("\n" + hr("═"));
  console.log("  Deployment Summary");
  console.log(hr("═"));
  console.log(`  Chain ID          : ${chainId}`);
  console.log(`  Block             : ${blockNumber}`);
  console.log(`  Deployer          : ${deployer.address}`);
  console.log(`  Deployed at       : ${deployedAt}`);
  console.log(hr());
  console.log(`  AttestationVault  : ${vaultAddress}`);
  console.log(`  BondManager       : ${bondManagerAddress}`);
  console.log(`  DisputeInsurance  : ${insuranceAddress}`);
  console.log(`  SentinelRegistry  : ${registryAddress}`);
  console.log(hr());
  console.log(`  ArcScan links:`);
  console.log(`    AttestationVault  → ${ARCSCAN_BASE}/${vaultAddress}`);
  console.log(`    BondManager       → ${ARCSCAN_BASE}/${bondManagerAddress}`);
  console.log(`    DisputeInsurance  → ${ARCSCAN_BASE}/${insuranceAddress}`);
  console.log(`    SentinelRegistry  → ${ARCSCAN_BASE}/${registryAddress}`);
  console.log(hr("═") + "\n");
}

// ─────────────────────────────────────────────────────────────────────────────
// Entry point
// ─────────────────────────────────────────────────────────────────────────────

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
