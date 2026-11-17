"""
Configuration Loader for FLOP Network Community Bot.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Reads environment variables from .env or system environment, with
automatic presets for FLOP Devnet and Testnet.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
    # Load .env from current directory or parent directory
    env_path = Path(".env")
    if env_path.exists():
        load_dotenv(env_path)
    else:
        load_dotenv()
except ImportError:
    pass

# Network defaults
NETWORK_PRESETS = {
    "devnet": {
        "rpc_url": "https://rpc.devnet.flop.network",
        "gateway_url": "https://api.flop.network/v1",
        "faucet_url": "https://faucet.flop.network/fund",
        "genesis_hash": "0x99c172c095340ace980631f9123544c6bebd4839f3437e463533422d8be2d631",
    },
    "testnet": {
        "rpc_url": "https://rpc.testnet.flop.network",
        "gateway_url": "https://api.testnet.flop.network/v1",
        "faucet_url": "https://faucet.testnet.flop.network/fund",
        "genesis_hash": "",
    },
}


@dataclass
class BotConfig:
    network: str
    rpc_url: str
    gateway_url: str
    faucet_url: str
    private_key_hex: str
    flop_model: str
    # AI task builder settings
    ai_builder_enabled: bool
    ai_builder_provider: str
    ai_builder_api_key: str
    ai_builder_model: str
    ai_builder_endpoint: str
    # Runtime settings
    loop_interval_seconds: float
    min_required_balance_flop: float
    max_turns_per_session: int
    data_dir: Path

    @classmethod
    def load(cls) -> "BotConfig":
        network = os.environ.get("FLOP_NETWORK", "devnet").lower().strip()
        preset = NETWORK_PRESETS.get(network, NETWORK_PRESETS["devnet"])

        rpc_url = os.environ.get("FLOP_RPC_URL") or preset["rpc_url"]
        gateway_url = os.environ.get("FLOP_GATEWAY_URL") or preset["gateway_url"]
        faucet_url = os.environ.get("FLOP_FAUCET_URL") or preset["faucet_url"]

        raw_key = os.environ.get("FLOP_PRIVATE_KEY", "").strip()
        # Clean potential 0x or quotes
        clean_key = raw_key.removeprefix("0x").strip('"\'')

        flop_model = os.environ.get("FLOP_MODEL", "qwen/qwen2.5-0.5b-instruct").strip()

        ai_enabled = os.environ.get("AI_BUILDER_ENABLED", "false").lower() in ("1", "true", "yes")
        ai_provider = os.environ.get("AI_BUILDER_PROVIDER", "groq").lower().strip()
        ai_key = os.environ.get("AI_BUILDER_API_KEY", "").strip()
        ai_model = os.environ.get("AI_BUILDER_MODEL", "llama-3.3-70b-versatile").strip()
        ai_endpoint = os.environ.get("AI_BUILDER_ENDPOINT", "https://api.groq.com/openai/v1").strip()

        loop_interval = float(os.environ.get("LOOP_INTERVAL_SECONDS", "30.0"))
        min_balance = float(os.environ.get("MIN_REQUIRED_BALANCE_FLOP", "1.0"))
        max_turns = int(os.environ.get("MAX_TURNS_PER_SESSION", "5"))

        data_dir = Path("data")
        data_dir.mkdir(parents=True, exist_ok=True)

        return cls(
            network=network,
            rpc_url=rpc_url.rstrip("/"),
            gateway_url=gateway_url.rstrip("/"),
            faucet_url=faucet_url.rstrip("/"),
            private_key_hex=clean_key,
            flop_model=flop_model,
            ai_builder_enabled=ai_enabled,
            ai_builder_provider=ai_provider,
            ai_builder_api_key=ai_key,
            ai_builder_model=ai_model,
            ai_builder_endpoint=ai_endpoint,
            loop_interval_seconds=loop_interval,
            min_required_balance_flop=min_balance,
            max_turns_per_session=max_turns,
            data_dir=data_dir,
        )
