"""Oracle Sentinel configuration — loads from ../.env"""
from __future__ import annotations
import json
import structlog
from pathlib import Path
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

log = structlog.get_logger()

# Arc Testnet contract addresses
USDC_ADDRESS = "0x3600000000000000000000000000000000000000"
EURC_ADDRESS = "0x89B50855Aa3bE2F677cD6303Cec089B5F319D72a"
USYC_ADDRESS = "0xe9185F0c5F296Ed1797AaE4238D26CCaBEadb86C"
USYC_TELLER = "0x9fdF14c5B14173D74C08Af27AebFf39240dC105A"
USYC_ENTITLEMENTS = "0xcc205224862c7641930c87679e98999d23c26113"
CCTP_TOKEN_MESSENGER = "0x8FE6B999Dc680CcFDD5Bf7EB0974218be2542DAA"
CCTP_MESSAGE_TRANSMITTER = "0xE737e5cEBEEBa77EFE34D4aa090756590b1CE275"
IDENTITY_REGISTRY = "0x8004A818BFB912233c491871b3d84c89A494BD9e"
REPUTATION_REGISTRY = "0x8004B663056A597Dffe9eCcC1965A193B7388713"
VALIDATION_REGISTRY = "0x8004Cb1BF31DAf7788923b405b754f57acEB4272"
AGENTIC_COMMERCE = "0x0747EEf0706327138c69792bF28Cd525089e4583"
ARC_CHAIN_ID = 5042002
ARC_BLOCK_EXPLORER = "https://testnet.arcscan.app"

POLYMARKET_CLOB_API = "https://clob.polymarket.com"
POLYMARKET_GAMMA_API = "https://gamma-api.polymarket.com"
POLYMARKET_WS = "wss://ws-subscriptions-clob.polymarket.com/ws/market"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../.env", env_file_encoding="utf-8", extra="ignore"
    )

    # Arc
    arc_rpc_key: str = ""
    arc_rpc_url: str = ""
    arc_chain_id: int = ARC_CHAIN_ID
    deployer_private_key: str = ""

    # Circle
    circle_api_key: str = ""
    circle_entity_secret: str = ""

    # AI
    groq_api_key: str = ""
    anthropic_api_key: str = ""

    # Evidence
    news_api_key: str = ""

    # Polymarket
    polymarket_builder_code: str = ""
    polymarket_clob_api: str = POLYMARKET_CLOB_API
    polymarket_gamma_api: str = POLYMARKET_GAMMA_API

    # Deployed contracts (auto-loaded from deployed-addresses.json)
    attestation_vault_address: str = ""
    bond_manager_address: str = ""
    sentinel_registry_address: str = ""

    # Agent behavior
    scout_interval_seconds: int = 30
    dispute_deviation_threshold: float = 0.40
    judge_confidence_threshold: float = 0.55
    max_markets_monitored: int = 200
    usyc_deploy_threshold_usdc: float = 50.0
    agent_bond_amount_usdc: float = 10.0

    @model_validator(mode="after")
    def _post_init(self) -> "Settings":
        if not self.arc_rpc_url and self.arc_rpc_key:
            self.arc_rpc_url = (
                f"https://rpc.testnet.arc-node.thecanteenapp.com/v1/{self.arc_rpc_key}"
            )
        if not self.attestation_vault_address:
            self._load_deployed_addresses()
        return self

    def _load_deployed_addresses(self) -> None:
        addr_file = Path("../deployed-addresses.json")
        if not addr_file.exists():
            addr_file = Path("deployed-addresses.json")
        if addr_file.exists():
            try:
                data = json.loads(addr_file.read_text())
                self.attestation_vault_address = data.get("attestationVault", "")
                self.bond_manager_address = data.get("bondManager", "")
                self.sentinel_registry_address = data.get("sentinelRegistry", "")
            except Exception as e:
                log.warning("failed_loading_deployed_addresses", error=str(e))


def _configure_structlog() -> None:
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


_configure_structlog()

settings = Settings()


def load_abi(contract_name: str) -> list:
    """Load ABI from compiled Hardhat artifacts."""
    # Try multiple possible artifact locations
    candidates = [
        Path(
            f"../contracts/artifacts/contracts/{contract_name}.sol/{contract_name}.json"
        ),
        Path(
            f"contracts/artifacts/contracts/{contract_name}.sol/{contract_name}.json"
        ),
    ]
    for path in candidates:
        if path.exists():
            data = json.loads(path.read_text())
            return data["abi"]
    # Return minimal ABI stubs if artifacts not compiled yet
    log.warning("abi_not_found", contract=contract_name)
    return []
