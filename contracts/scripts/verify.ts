import hre from "hardhat";
import fs from "fs";
import path from "path";

// ─────────────────────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────────────────────

const PROJECT_ROOT = path.resolve(__dirname, "..", "..");
const ADDRESSES_FILE = path.join(PROJECT_ROOT, "deployed-addresses.json");

const ARCSCAN_BASE = "https://testnet.arcscan.app/address";

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

interface ContractVerifySpec {
  name: string;
  address: string;
  constructorArguments: unknown[];
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

/** Print a horizontal separator. */
function hr(char = "─", width = 68): string {
  return char.repeat(width);
}

/** Returns true when the error indicates the contract is already verified. */
function isAlreadyVerified(err: unknown): boolean {
  const msg = (err instanceof Error ? err.message : String(err)).toLowerCase();
  return (
    msg.includes("already verified") ||
    msg.includes("already been verified") ||
    msg.includes("contract source code already verified") ||
    msg.includes("smart-contract already verified")
  );
}

/** Attempt to verify a single contract, handling already-verified gracefully. */
async function verifyContract(spec: ContractVerifySpec): Promise<void> {
  const { name, address, constructorArguments } = spec;
  const link = `${ARCSCAN_BASE}/${address}`;

  console.log(`\n${hr()}`);
  console.log(`Verifying ${name}`);
  console.log(`  Address : ${address}`);
  console.log(`  ArcScan : ${link}`);
  console.log(`  Args    : ${JSON.stringify(constructorArguments)}`);

  try {
    await hre.run("verify:verify", {
      address,
      constructorArguments,
    });
    console.log(`  ✅ ${name} verified successfully`);
  } catch (err) {
    if (isAlreadyVerified(err)) {
      console.log(`  ℹ️  ${name} is already verified — skipping`);
    } else {
      // Log error but do not rethrow — partial verification is recoverable
      console.error(
        `  ✗ ${name} verification failed: ${(err as Error).message ?? err}`
      );
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Main
// ─────────────────────────────────────────────────────────────────────────────

async function main(): Promise<void> {
  console.log("\n" + hr("═"));
  console.log("  Oracle Sentinel — Contract Verification Script");
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
  console.log(`  Deployed at      : ${addresses.deployedAt}`);
  console.log(`  Chain ID         : ${addresses.chainId}`);
  console.log(`  Deployer         : ${addresses.deployer}`);
  console.log(`  Block number     : ${addresses.blockNumber}`);
  console.log(`  AttestationVault : ${addresses.attestationVault}`);
  console.log(`  BondManager      : ${addresses.bondManager}`);
  console.log(`  SentinelRegistry : ${addresses.sentinelRegistry}`);

  // ── Build verify specs ────────────────────────────────────────────────────────
  //
  // Constructor signatures (from Solidity):
  //   AttestationVault(address initialOwner)
  //   BondManager(address initialOwner, address _attestationVault)
  //   OracleSentinelRegistry(address initialOwner, address _vault, address _bondManager)
  //
  const specs: ContractVerifySpec[] = [
    {
      name: "AttestationVault",
      address: addresses.attestationVault,
      constructorArguments: [addresses.deployer],
    },
    {
      name: "BondManager",
      address: addresses.bondManager,
      constructorArguments: [addresses.deployer, addresses.attestationVault],
    },
    {
      name: "OracleSentinelRegistry",
      address: addresses.sentinelRegistry,
      constructorArguments: [
        addresses.deployer,
        addresses.attestationVault,
        addresses.bondManager,
      ],
    },
  ];

  // ── Verify each contract ──────────────────────────────────────────────────────
  let verified = 0;
  let skipped = 0;
  let failed = 0;

  for (const spec of specs) {
    const beforeErrors = process.exitCode;
    try {
      await verifyContract(spec);
      verified++;
    } catch {
      // verifyContract does not rethrow; this catch is a safety net
      failed++;
    }
  }

  // ── Summary ───────────────────────────────────────────────────────────────────
  console.log("\n" + hr("═"));
  console.log("  Verification Summary");
  console.log(hr("═"));
  for (const spec of specs) {
    console.log(`  ${spec.name.padEnd(25)} : ${ARCSCAN_BASE}/${spec.address}`);
  }
  console.log(hr("═") + "\n");
}

// ─────────────────────────────────────────────────────────────────────────────
// Entry point
// ─────────────────────────────────────────────────────────────────────────────

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
