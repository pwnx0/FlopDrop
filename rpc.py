"""
Substrate JSON-RPC and Explorer Client for FLOP Network.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
HTTP client for FLOP Substrate nodes and the explorer API.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict, Optional
import httpx

logger = logging.getLogger("FlopRpc")


class FlopRpcClient:
    """Client for Substrate JSON-RPC and explorer balance checks."""

    def __init__(self, rpc_url: str, explorer_api: Optional[str] = None, timeout: float = 15.0) -> None:
        self.rpc_url = rpc_url.rstrip("/")
        # Derive explorer API if not provided
        if not explorer_api:
            if "testnet" in self.rpc_url:
                explorer_api = "https://explorer.testnet.flop.network/api"
            else:
                explorer_api = "https://explorer.devnet.flop.network/api"
        self.explorer_api = explorer_api.rstrip("/")
        self.timeout = timeout

    def call_rpc(self, method: str, params: Optional[list] = None) -> Any:
        """Execute a standard Substrate JSON-RPC 2.0 call."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or [],
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(self.rpc_url, json=payload, headers={"Content-Type": "application/json"})
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                raise RuntimeError(f"Substrate RPC error: {data['error']}")
            return data.get("result")

    def get_chain_name(self) -> str:
        """Query chain name from Substrate node (e.g. 'FLOP Devnet')."""
        return str(self.call_rpc("system_chain"))

    def get_genesis_hash(self) -> str:
        """Query genesis block hash (block 0)."""
        return str(self.call_rpc("chain_getBlockHash", [0]))

    def get_wallet_balance(self, address: str) -> Optional[Decimal]:
        """Fetch confirmed on-chain balance in FLOP (18 decimal scaling)."""
        # Primary: Query Explorer / Accounts REST endpoint
        url = f"{self.explorer_api}/accounts/{address}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, headers={"User-Agent": "FlopCommunityBot/1.0"})
                if resp.status_code == 200:
                    data = resp.json()
                    raw_bal = data.get("balance", "0")
                    # FLOP uses 18 decimals
                    bal = Decimal(str(raw_bal)) / Decimal(10**18)
                    return bal
        except Exception as exc:
            logger.debug("Explorer balance check failed for %s: %s", address[:8], exc)

        return None
