"""Oracle Sentinel Discord Bot — F8
Slash commands for querying prediction market analysis, leaderboards,
war-room alerts, and triggering the Scout→Judge attestation pipeline.
"""

from __future__ import annotations

import os
import uuid
import logging
from typing import Any

import httpx
import discord
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger("oracle_sentinel.discord")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

DISCORD_TOKEN: str = os.environ["DISCORD_TOKEN"]
API_BASE: str = os.getenv("ORACLE_SENTINEL_API_URL", "http://localhost:8000")
FOOTER_TEXT = "Oracle Sentinel · Arc Testnet · Powered by Circle"

# ── Colour palette ────────────────────────────────────────────────────────────
COLOR_GREEN = 0x2ECC71   # YES / resolved true
COLOR_RED = 0xE74C3C     # NO  / resolved false
COLOR_YELLOW = 0xF1C40F  # UNCERTAIN / pending
COLOR_BLUE = 0x3498DB    # neutral info
COLOR_ORANGE = 0xE67E22  # warning / alert


def _outcome_color(outcome: str | None) -> int:
    """Map a textual outcome to an embed colour."""
    if outcome is None:
        return COLOR_YELLOW
    o = outcome.upper()
    if o in {"YES", "TRUE", "RESOLVED_YES"}:
        return COLOR_GREEN
    if o in {"NO", "FALSE", "RESOLVED_NO"}:
        return COLOR_RED
    return COLOR_YELLOW


def _footer(embed: discord.Embed) -> discord.Embed:
    embed.set_footer(text=FOOTER_TEXT)
    return embed


def _offline_embed() -> discord.Embed:
    e = discord.Embed(
        title="System Offline",
        description="Oracle Sentinel API is unreachable. Check back soon.",
        color=COLOR_ORANGE,
    )
    _footer(e)
    return e


async def _get(path: str, params: dict[str, Any] | None = None) -> dict | list | None:
    """Perform a GET against the backend; return None on any error."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{API_BASE}{path}", params=params or {})
            r.raise_for_status()
            return r.json()
    except Exception as exc:
        log.warning("GET %s failed: %s", path, exc)
        return None


async def _post(path: str, body: dict) -> dict | None:
    """Perform a POST against the backend; return None on any error."""
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(f"{API_BASE}{path}", json=body)
            r.raise_for_status()
            return r.json()
    except Exception as exc:
        log.warning("POST %s failed: %s", path, exc)
        return None


# ── Discord client setup ──────────────────────────────────────────────────────

class OracleSentinelBot(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        await self.tree.sync()
        log.info("Slash commands synced globally.")

    async def on_ready(self) -> None:
        log.info("Bot ready — logged in as %s (id=%s)", self.user, self.user.id)
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="prediction markets · /sentinel",
            )
        )


client = OracleSentinelBot()


# ── /sentinel <market_url_or_id> ──────────────────────────────────────────────

@client.tree.command(name="sentinel", description="Fetch Oracle Sentinel analysis for a Polymarket URL or market ID")
@app_commands.describe(market_url_or_id="Polymarket URL or numeric market ID")
async def sentinel(interaction: discord.Interaction, market_url_or_id: str) -> None:
    await interaction.response.defer(thinking=True)

    # Extract a bare market ID if a full URL was pasted
    market_id = market_url_or_id.strip()
    if market_id.startswith("http"):
        # e.g. https://polymarket.com/event/will-X/...?id=12345
        for part in market_id.split("/"):
            if part.isdigit():
                market_id = part
                break
        else:
            # Fall back: try query param
            if "id=" in market_id:
                market_id = market_id.split("id=")[-1].split("&")[0]

    # 1. Fetch attestations for the market
    data = await _get("/api/attestations", {"market_id": market_id, "limit": 5})
    if data is None:
        await interaction.followup.send(embed=_offline_embed())
        return

    attestations: list[dict] = data if isinstance(data, list) else data.get("attestations", [])

    # 2. Also try to get the market meta
    markets_data = await _get("/api/markets", {"limit": 50})
    market_meta: dict | None = None
    if markets_data:
        all_markets: list[dict] = markets_data if isinstance(markets_data, list) else markets_data.get("markets", [])
        for m in all_markets:
            if str(m.get("id", "")) == str(market_id) or str(m.get("market_id", "")) == str(market_id):
                market_meta = m
                break

    question = (market_meta or {}).get("question", f"Market {market_id}")
    outcome = (attestations[0].get("outcome") if attestations else None)
    confidence = (attestations[0].get("confidence") if attestations else None)

    embed = discord.Embed(
        title=f"Oracle Analysis — {question[:200]}",
        url=market_url_or_id if market_url_or_id.startswith("http") else discord.utils.MISSING,
        color=_outcome_color(outcome),
    )
    embed.add_field(name="Market ID", value=f"`{market_id}`", inline=True)
    embed.add_field(name="Outcome", value=outcome or "Pending", inline=True)
    if confidence is not None:
        embed.add_field(name="Confidence", value=f"{confidence:.1%}" if isinstance(confidence, float) else str(confidence), inline=True)

    if attestations:
        lines = []
        for att in attestations[:5]:
            agent = att.get("agent_id", att.get("agent", "unknown"))
            o = att.get("outcome", "?")
            c = att.get("confidence", "")
            conf_str = f" ({c:.1%})" if isinstance(c, float) else (f" ({c})" if c else "")
            lines.append(f"• **{agent}** → {o}{conf_str}")
        embed.add_field(name=f"Latest Attestations ({len(attestations)})", value="\n".join(lines), inline=False)
    else:
        embed.add_field(name="Attestations", value="None found for this market yet.", inline=False)

    if market_meta:
        if market_meta.get("resolution_date"):
            embed.add_field(name="Resolves", value=market_meta["resolution_date"], inline=True)
        if market_meta.get("volume"):
            embed.add_field(name="Volume", value=f"${market_meta['volume']:,.0f}", inline=True)

    _footer(embed)
    await interaction.followup.send(embed=embed)


# ── /leaderboard ──────────────────────────────────────────────────────────────

@client.tree.command(name="leaderboard", description="Top-5 agent calibration scores")
async def leaderboard(interaction: discord.Interaction) -> None:
    await interaction.response.defer(thinking=True)

    data = await _get("/api/calibration/stats")
    if data is None:
        await interaction.followup.send(embed=_offline_embed())
        return

    agents: list[dict] = []
    if isinstance(data, list):
        agents = data
    elif isinstance(data, dict):
        agents = data.get("agents", data.get("leaderboard", data.get("stats", [])))
        # Some backends return a flat dict keyed by agent
        if not agents and any(isinstance(v, dict) for v in data.values()):
            agents = [{"agent_id": k, **v} for k, v in data.items() if isinstance(v, dict)]

    agents = agents[:5]

    embed = discord.Embed(
        title="Agent Calibration Leaderboard",
        description="Top 5 agents ranked by Brier score accuracy",
        color=COLOR_BLUE,
    )

    medals = ["🥇", "🥈", "🥉", "4.", "5."]
    for rank, agent in enumerate(agents):
        name = agent.get("agent_id", agent.get("agent", agent.get("name", f"Agent {rank + 1}")))
        brier = agent.get("brier_score", agent.get("calibration_score", agent.get("score")))
        total = agent.get("total_attestations", agent.get("attestations", ""))
        accuracy = agent.get("accuracy", "")

        val_parts = []
        if brier is not None:
            val_parts.append(f"Brier: `{brier:.4f}`" if isinstance(brier, float) else f"Brier: `{brier}`")
        if accuracy:
            val_parts.append(f"Accuracy: `{accuracy:.1%}`" if isinstance(accuracy, float) else f"Accuracy: `{accuracy}`")
        if total:
            val_parts.append(f"Attestations: `{total}`")

        embed.add_field(
            name=f"{medals[rank]} {name}",
            value="\n".join(val_parts) if val_parts else "No stats available",
            inline=False,
        )

    if not agents:
        embed.description = "No calibration data available yet."

    _footer(embed)
    await interaction.followup.send(embed=embed)


# ── /warroom ──────────────────────────────────────────────────────────────────

@client.tree.command(name="warroom", description="Current top-3 active dispute alerts")
async def warroom(interaction: discord.Interaction) -> None:
    await interaction.response.defer(thinking=True)

    data = await _get("/api/watchdog/alerts")
    if data is None:
        await interaction.followup.send(embed=_offline_embed())
        return

    alerts: list[dict] = data if isinstance(data, list) else data.get("alerts", [])
    alerts = alerts[:3]

    embed = discord.Embed(
        title="War Room — Active Alerts",
        description="Top 3 disputes under Watchdog surveillance",
        color=COLOR_ORANGE,
    )

    severity_icons = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}

    for i, alert in enumerate(alerts, 1):
        severity = alert.get("severity", alert.get("level", "MEDIUM")).upper()
        icon = severity_icons.get(severity, "🟡")
        market_id = alert.get("market_id", "unknown")
        reason = alert.get("reason", alert.get("message", alert.get("description", "Suspicious activity detected")))
        flagged_at = alert.get("flagged_at", alert.get("created_at", alert.get("timestamp", "")))

        val_lines = [
            f"**Market:** `{market_id}`",
            f"**Severity:** {icon} {severity}",
            f"**Reason:** {reason[:200]}",
        ]
        if flagged_at:
            val_lines.append(f"**Flagged:** {str(flagged_at)[:19]}")

        embed.add_field(name=f"Alert #{i}", value="\n".join(val_lines), inline=False)

    if not alerts:
        embed.description = "No active alerts — all markets looking clean."
        embed.color = COLOR_GREEN

    _footer(embed)
    await interaction.followup.send(embed=embed)


# ── /attest <market_id> ───────────────────────────────────────────────────────

@client.tree.command(name="attest", description="Trigger Scout→Judge attestation pipeline for a market")
@app_commands.describe(market_id="The numeric or string market ID to attest")
async def attest(interaction: discord.Interaction, market_id: str) -> None:
    await interaction.response.defer(thinking=True)

    result = await _post("/api/agents/attest", {"market_id": market_id})
    if result is None:
        # Try alternative endpoint naming conventions
        result = await _post("/api/jobs/attest", {"market_id": market_id})
    if result is None:
        result = await _post("/api/agents/run", {"market_id": market_id, "pipeline": "scout_judge"})

    if result is None:
        embed = discord.Embed(
            title="Attestation Failed",
            description=(
                "Could not reach the Oracle Sentinel API to trigger the pipeline.\n"
                "Ensure the backend is running and try again."
            ),
            color=COLOR_RED,
        )
        _footer(embed)
        await interaction.followup.send(embed=embed)
        return

    job_id = result.get("job_id", result.get("id", str(uuid.uuid4())[:8]))
    status = result.get("status", "queued")
    msg = result.get("message", result.get("detail", "Pipeline dispatched successfully."))

    embed = discord.Embed(
        title="Attestation Pipeline Triggered",
        description=f"Scout → Judge pipeline launched for market `{market_id}`.",
        color=COLOR_BLUE,
    )
    embed.add_field(name="Job ID", value=f"`{job_id}`", inline=True)
    embed.add_field(name="Status", value=status.capitalize(), inline=True)
    if msg:
        embed.add_field(name="Details", value=str(msg)[:500], inline=False)

    embed.add_field(
        name="Contracts",
        value=(
            "AttestationVault: `0x4dE6AF7329E88F08C0560DAf1290a0DF152901E3`\n"
            "BondManager: `0x2274D05C24527D0e4b689b215ddEAfE51B319008`"
        ),
        inline=False,
    )

    _footer(embed)
    await interaction.followup.send(embed=embed)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    if not DISCORD_TOKEN:
        raise RuntimeError("DISCORD_TOKEN environment variable is not set.")
    log.info("Starting Oracle Sentinel Discord bot…")
    client.run(DISCORD_TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
