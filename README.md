# ⚡ ORACLE SENTINEL

> **The autonomous AI truth verification network that prediction markets never knew they needed — and can no longer survive without.**

**Agora Agents Hackathon | Canteen × Circle × Arc | May 2026**

---

## 🎬 See It Live — Watch the Demo First

<div align="center">

[![Oracle Sentinel Demo — Watch Now](https://img.youtube.com/vi/RMRh5-pO8iA/maxresdefault.jpg)](https://youtu.be/RMRh5-pO8iA)

### 👆 Click to watch — AI agents detecting oracle manipulation in real-time, committing immutable attestations to Arc Testnet

</div>

> **In this demo:** A Scout Agent detects a suspicious Polymarket resolution → Judge Agent synthesizes multi-source evidence via Bayesian inference → Attestation committed on-chain in under 10 seconds → Watchdog triggers an automated dispute before manipulation finalizes.

---

## The Problem

Prediction markets processed **$44 billion** in volume in 2025. But their resolution oracle layer is fatally broken:

- **March 2025**: A single whale used 25% of UMA voting power to falsely settle a $7M Polymarket contract on Ukraine's mineral deal — resolved YES with no agreement signed
- **December 2025**: A $16M UFO declassification market resolved YES with zero evidence of document release
- The UMA challenge window is 2 hours + 2-day vote. By the time humans notice manipulation, it has already finalized
- Every AI trading agent being built today will **inherit this broken oracle** and amplify losses at machine speed

## The Solution

ORACLE SENTINEL is a three-tier autonomous agent network that:

1. **Scout Agents** — Crawl multi-source evidence for every active Polymarket market in real-time (news, on-chain data, Wayback Machine, market microstructure, social sentiment)
2. **Judge Agent** — Synthesizes a cryptographically verified resolution recommendation with a calibrated confidence score using Bayesian inference
3. **Watchdog Agent** — Watches the UMA challenge window and auto-triggers a dispute in under 2 seconds when manipulation is detected

## Architecture

```
Polymarket Markets → Scout Agents (5 parallel sources)
                           ↓
                    Judge Agent (LangGraph + Bayesian)
                           ↓
                  AttestationVault (Arc Testnet, $0.01/attestation)
                           ↓
                    IPFS (Irys) — full reasoning trace
                           ↓
              Watchdog Agent → UMA dispute trigger
```

## Circle Tools Used

| Tool | Usage |
|------|-------|
| **ERC-8004 Agent Identity** | Each agent (Scout, Judge, Watchdog) has an on-chain identity with reputation scoring |
| **ERC-8183 Agentic Commerce** | Market creators can post jobs; agents earn USDC on completion |
| **Developer-Controlled Wallets** | Three SCA wallets (one per agent) managed via Circle API |
| **USYC** | Idle USDC automatically deployed to tokenized money market fund for yield |
| **Arc Testnet** | All attestations + reputation events committed on-chain for ~$0.01/attestation |

## Quick Start

### Prerequisites
- Node.js 18+, Python 3.11+, Yarn
- Arc Testnet RPC key (from Canteen)
- Circle Developer API key
- Groq API key (free tier)
- NewsAPI key (free tier)

### Setup

```bash
# 1. Clone and configure
cp .env.example .env
# Fill in all values in .env

# 2. Install dependencies
yarn install
yarn agents:install

# 3. Deploy contracts to Arc Testnet
yarn contracts:compile
yarn contracts:deploy

# 4. Register agents on-chain
cd contracts && npx hardhat run scripts/register-agents.ts --network arcTestnet

# 5. Start backend + agents
yarn backend:start &
yarn agents:start &

# 6. Start frontend
yarn frontend:dev
```

### Running Agents

```bash
cd agents
python main.py
```

The agent system will:
1. Create/load Circle Developer-Controlled Wallets for each agent
2. Register agents on ERC-8004 IdentityRegistry
3. Fetch the top 200 active Polymarket markets
4. Begin continuous scouting, judging, and watchdog monitoring

## Project Structure

```
oracle-sentinel/
├── contracts/          # Solidity contracts + Hardhat
│   ├── AttestationVault.sol
│   ├── BondManager.sol
│   └── OracleSentinelRegistry.sol
├── agents/             # Python autonomous agents
│   ├── scout/          # Multi-source evidence gathering
│   ├── judge/          # Bayesian synthesis + LangGraph
│   ├── watchdog/       # UMA manipulation detection
│   ├── arc/            # Arc + Circle integrations
│   ├── polymarket/     # Polymarket API clients
│   └── storage/        # SQLite persistence
├── backend/            # FastAPI REST + WebSocket
└── frontend/           # Next.js dashboard
```

## How It Earns

- **Arc Attestations**: Market creators pay $0.01–$1.00/attestation for verified resolution evidence
- **ERC-8183 Jobs**: Market creators post jobs with USDC escrow; agents earn on completion
- **USYC Yield**: Idle USDC deployed to Circle's tokenized money market fund
- **Polymarket Builder Fees**: Fee share on every trade originating from Sentinel intelligence

## Traction

From day 1, ORACLE SENTINEL monitors **200 live Polymarket markets** — zero user acquisition needed. Every resolution produces an immutable Arc attestation, building a calibration track record that compounds in value over time.

## Team

Built at the Agora Agents Hackathon, May 2026.

---

## 🚀 Links

<div align="center">

| 🎬 Demo Video | 🔍 ArcScan Explorer | 📖 API Docs |
|:---:|:---:|:---:|
| [Watch on YouTube](https://youtu.be/RMRh5-pO8iA) | [testnet.arcscan.app](https://testnet.arcscan.app) | [Live API](https://oracle-sentinel.onrender.com/docs) |

</div>

---

<div align="center">

**⚡ Built with Arc Testnet · Circle USDC · Polymarket · LangGraph · Groq**

*Every oracle lie leaves a trace. Oracle Sentinel finds it.*

</div>
