"""
StableArch Council - Off-Chain Orchestration Platform
the Issuing Bank | Cari Network | ZKsync Prividium

Configuration module: loads settings from environment / .env file.

Cari Deposit Account (CDA) = on-chain representation of a Demand Deposit Account (DDA).
DDA <-> CDA flow: fiat in DDA triggers CDA mint; CDA burn triggers fiat back to DDA.
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class Environment(str, Enum):
    DEV = "dev"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # --- App ---
    app_name: str = "the Issuing Bank Cari Deposit Orchestrator"
    environment: Environment = Environment.DEV
    debug: bool = True
    api_prefix: str = "/api/v1"

    # --- ZKsync Prividium ---
    prividium_rpc_url: str = "https://sepolia.era.zksync.dev"
    chain_id: int = 300  # ZKsync Sepolia; Prividium mainnet will differ
    token_contract_address: str = ""
    oracle_contract_address: str = ""
    settlement_contract_address: str = ""
    compliance_oracle_address: str = ""

    # --- Signing / HSM ---
    # In production, keys are in AWS CloudHSM / Azure Key Vault.
    # These are LOCAL-DEV-ONLY fallbacks and MUST be empty in production.
    minter_private_key: str = ""
    burner_private_key: str = ""
    attestor_private_key: str = ""
    compliance_private_key: str = ""
    settlement_private_key: str = ""

    # Operator (Cari Whitepaper: centralized CDA supply controller)
    operator_address: str = ""              # Operator's on-chain address
    operator_private_key: str = ""          # LOCAL-DEV-ONLY — Operator signing key
    hsm_key_id_operator: str = ""           # Production HSM key for Operator

    # HSM config (production)
    hsm_provider: str = ""  # "aws_cloudhsm" | "azure_keyvault"
    hsm_key_id_minter: str = ""
    hsm_key_id_burner: str = ""
    hsm_key_id_attestor: str = ""

    # --- Core Banking ---
    core_banking_base_url: str = "https://corebanking.internal.issuing-bank.com/api"
    core_banking_api_key: str = ""

    # --- Custody ---
    fireblocks_api_key: str = ""
    fireblocks_api_secret_path: str = ""
    fireblocks_vault_id: str = ""
    coinbase_custody_api_key: str = ""

    # --- Kafka ---
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic_transactions: str = "cari.transactions"
    kafka_topic_compliance: str = "cari.compliance"
    kafka_topic_settlements: str = "cari.settlements"
    kafka_consumer_group: str = "cari-orchestrator"

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"

    # --- Compliance ---
    chainalysis_api_key: str = ""
    chainalysis_base_url: str = "https://api.chainalysis.com/api/kyt/v2"
    notabene_api_key: str = ""
    notabene_base_url: str = "https://api.notabene.id/tf"
    travel_rule_threshold_usd: int = 3_000

    # --- Reserve Oracle ---
    reserve_staleness_seconds: int = 86_400  # 24h
    reserve_rebalance_threshold_pct: float = 5.0  # alert if deviation > 5%

    # --- Database ---
    database_url: str = "sqlite+aiosqlite:///./cari_orchestrator.db"

    # --- CORS ---
    # Allowed origins for non-DEV environments (must be explicitly configured for production)
    cors_allowed_origins: list[str] = Field(default_factory=list, description="Explicit CORS origins for staging/production")

    # --- Rate Limiting ---
    rate_limit_default: str = "60/minute"  # Default rate limit for all endpoints
    rate_limit_transactions: str = "30/minute"  # Stricter limit for mint/burn
    rate_limit_health: str = "120/minute"  # More lenient for health checks

    model_config = {"env_prefix": "CARI_", "env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
