"""
FLOP Public Inference Gateway Client.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
HTTP client for the FLOP Public Inference API (https://api.flop.network/v1):
- Challenge requesting and Ed25519 wallet signing.
- Bearer token caching.
- OpenAI-compatible chat completions with dynamic model selection and token tracking.
- Direct faucet claiming helper.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import httpx

from crypto import sign_message

logger = logging.getLogger("FlopClient")


class FlopGatewayError(RuntimeError):
    """Base error for gateway failures."""
    pass


class FlopRateLimitError(FlopGatewayError):
    """Raised on HTTP 429 with optional Retry-After hint."""
    def __init__(self, message: str, retry_after: Optional[float] = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class FlopCapReachedError(FlopGatewayError):
    """Raised on HTTP 503 when daily enrollment cap is reached."""
    def __init__(self, message: str, retry_after: Optional[float] = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class FlopAuthError(FlopGatewayError):
    """Raised on HTTP 401 when bearer token is invalid or expired."""
    pass


class FlopNodeOverloadedError(FlopGatewayError):
    """Raised on HTTP 502/504 or timeouts when FLOP GPU inference nodes are busy or restarting."""
    def __init__(self, message: str, retry_after: Optional[float] = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class FlopGatewayClient:
    """Official client for FLOP Public Inference Data Plane."""

    def __init__(
        self,
        base_url: str,
        faucet_url: str,
        cache_path: Optional[Path] = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.faucet_url = faucet_url.rstrip("/")
        self.timeout = timeout
        self.cache_path = cache_path or Path("data/bearer_cache.json")

    # ----------------------------------------------------------- Token Cache
    def get_cached_bearer(self, address: str) -> Optional[str]:
        """Load stored bearer token if still valid and unexpired."""
        if not self.cache_path.exists():
            return None
        try:
            data = json.loads(self.cache_path.read_text(encoding="utf-8"))
            record = data.get(address)
            if record and isinstance(record, dict):
                token = record.get("bearer_token")
                expires_at = record.get("expires_at", 0)
                if token and (expires_at == 0 or time.time() < expires_at):
                    return str(token)
        except Exception as exc:
            logger.debug("Failed reading bearer cache: %s", exc)
        return None

    def save_cached_bearer(self, address: str, bearer_token: str, quota: Any = None, ttl_seconds: float = 86400) -> None:
        """Persist bearer token to avoid re-enrolling on every run."""
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        if self.cache_path.exists():
            try:
                data = json.loads(self.cache_path.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        data[address] = {
            "bearer_token": bearer_token,
            "remaining_quota": str(quota) if quota is not None else None,
            "enrolled_at": time.time(),
            "expires_at": time.time() + ttl_seconds,
        }
        self.cache_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def invalidate_cached_bearer(self, address: str) -> None:
        """Invalidate cached token upon receiving HTTP 401."""
        if not self.cache_path.exists():
            return
        try:
            data = json.loads(self.cache_path.read_text(encoding="utf-8"))
            if address in data:
                del data[address]
                self.cache_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    # -------------------------------------------------------- Direct Network
    def check_health(self) -> bool:
        """Check if gateway is reachable via /models."""
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(f"{self.base_url}/models")
                return resp.status_code == 200
        except Exception:
            return False

    def list_models(self) -> List[Dict[str, Any]]:
        """List active admitted models available on FLOP network."""
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(f"{self.base_url}/models")
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", [])

    def request_challenge(self, address: str) -> str:
        """Request single-use enrollment challenge message."""
        url = f"{self.base_url}/enroll/wallet/challenge?address={address}"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()
            return data["message"]

    def enroll_wallet(self, address: str, private_key_hex: str) -> str:
        """Enroll wallet and obtain gateway Bearer token with local caching."""
        cached = self.get_cached_bearer(address)
        if cached:
            logger.info("Reusing cached gateway Bearer token for %s", address[:8] + "...")
            return cached

        logger.info("Enrolling wallet %s with FLOP Gateway...", address[:8] + "...")
        # 1. Request challenge
        message = self.request_challenge(address)

        # 2. Sign challenge with Ed25519
        sig_hex = sign_message(private_key_hex, message)

        # 3. Exchange signed challenge for bearer token
        url = f"{self.base_url}/enroll/wallet"
        payload = {
            "address": address,
            "message": message,
            "signature": sig_hex,
        }

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, json=payload)
            if resp.status_code == 503:
                retry_after = None
                try:
                    retry_after = float(resp.headers.get("Retry-After", "900"))
                except (ValueError, TypeError):
                    retry_after = 900.0
                raise FlopCapReachedError(f"Gateway enrollment cap reached: {resp.text}", retry_after=retry_after)
            resp.raise_for_status()
            data = resp.json()
            token = data.get("key")
            quota = data.get("remaining_quota", 25.0)
            if not token:
                raise FlopGatewayError(f"Enrollment response missing key: {data}")

            self.save_cached_bearer(address, token, quota=quota)
            logger.info("Successfully enrolled! Quota: %s FLOP", quota)
            return token

    def chat_completion(
        self,
        bearer_token: str,
        model: str,
        messages: List[Dict[str, str]],
        max_tokens: int = 512,
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Execute chat completion using verified allowance."""
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json",
            "User-Agent": "FlopCommunityBot/1.0",
        }
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if temperature is not None:
            payload["temperature"] = temperature

        # Inference on decentralized GPU nodes needs a higher timeout (60s)
        inference_timeout = max(self.timeout, 60.0)
        try:
            with httpx.Client(timeout=inference_timeout) as client:
                resp = client.post(url, json=payload, headers=headers)
                if resp.status_code == 401:
                    raise FlopAuthError(f"Gateway rejected bearer token (401): {resp.text}")
                if resp.status_code == 429:
                    retry_after = None
                    try:
                        retry_after = float(resp.headers.get("Retry-After", "30"))
                    except (ValueError, TypeError):
                        retry_after = 30.0
                    raise FlopRateLimitError(f"Gateway rate limited (429): {resp.text}", retry_after=retry_after)
                if resp.status_code in (502, 503, 504):
                    raise FlopNodeOverloadedError(
                        f"FLOP GPU inference node busy/recovering (HTTP {resp.status_code})",
                        retry_after=45.0,
                    )
                resp.raise_for_status()
                return resp.json()
        except httpx.TimeoutException as exc:
            raise FlopNodeOverloadedError(
                f"FLOP GPU inference timed out after {inference_timeout:.0f}s (node queue busy).",
                retry_after=30.0,
            ) from exc

    def claim_faucet(self, address: str) -> Dict[str, Any]:
        """Direct faucet request to fund devnet/testnet wallet."""
        url = self.faucet_url
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "FlopCommunityBot/1.0",
        }
        payload = {"address": address}
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(url, json=payload, headers=headers)
            data = resp.json() if resp.status_code == 200 else {"status": resp.status_code, "text": resp.text}
            return data
