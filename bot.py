"""
Bot runtime for the FLOP Network.

Handles:
- Wallet balance verification on Substrate L1.
- Gateway enrollment and bearer token caching.
- Task generation (Trade Decision & Web3 Analysis) with AI refinement.
- Authenticated FLOP Gateway inference execution.
- Adaptive backoff on HTTP 429 / 503 limits.
- Persistent local SQLite receipts ledger.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Optional

from ai_builder import AITaskSynthesizer
from client import (
    FlopAuthError,
    FlopCapReachedError,
    FlopGatewayClient,
    FlopNodeOverloadedError,
    FlopRateLimitError,
)
from config import BotConfig
from crypto import private_key_to_ss58
from rpc import FlopRpcClient
from task_builder import BaseTask

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [FlopBot] %(message)s",
)
logger = logging.getLogger("FlopBot")


class FlopCommunityBot:
    """Production-ready community bot executing tasks on FLOP Network."""

    def __init__(self, config: BotConfig) -> None:
        self.config = config
        if not self.config.private_key_hex:
            raise ValueError(
                "FLOP_PRIVATE_KEY is missing in .env! "
                "Run `python main.py --generate-wallet` to generate a wallet or add your hex key."
            )

        # Derive SS58 address
        self.address = private_key_to_ss58(self.config.private_key_hex)
        self.address_short = f"{self.address[:8]}...{self.address[-4:]}"

        # Initialize clients (Direct connection, no proxies)
        self.rpc = FlopRpcClient(rpc_url=self.config.rpc_url)
        self.gateway = FlopGatewayClient(
            base_url=self.config.gateway_url,
            faucet_url=self.config.faucet_url,
            cache_path=self.config.data_dir / "bearer_cache.json",
        )
        self.ai_synthesizer = AITaskSynthesizer(self.config)
        self.db_path = self.config.data_dir / "flop_bot.db"
        self._init_db()

        self._bearer_token: Optional[str] = None
        self._cooldown_until: float = 0.0
        self._cached_balance: Optional[Decimal] = None
        self._last_balance_check: float = 0.0
        self._last_faucet_attempt: float = 0.0

    def _init_db(self) -> None:
        """Initialize local SQLite ledger for completed execution receipts."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS completed_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT UNIQUE NOT NULL,
                    category TEXT NOT NULL,
                    title TEXT NOT NULL,
                    model TEXT NOT NULL,
                    prompt_tokens INTEGER NOT NULL,
                    completion_tokens INTEGER NOT NULL,
                    total_tokens INTEGER NOT NULL,
                    response_text TEXT NOT NULL,
                    latency_ms REAL NOT NULL,
                    timestamp REAL NOT NULL
                );
                """
            )

    def log_receipt(
        self,
        task: BaseTask,
        model: str,
        total_tokens: int,
        prompt_tokens: int,
        completion_tokens: int,
        response_text: str,
        latency_ms: float,
    ) -> None:
        """Persist execution receipt locally."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO completed_tasks (
                    task_id, category, title, model,
                    prompt_tokens, completion_tokens, total_tokens,
                    response_text, latency_ms, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    task.task_id,
                    task.category,
                    task.title,
                    model,
                    prompt_tokens,
                    completion_tokens,
                    total_tokens,
                    response_text,
                    latency_ms,
                    time.time(),
                ),
            )

    def print_status(self) -> Dict[str, Any]:
        """Print full diagnostics for network, balance, and gateway enrollment."""
        print("\n" + "=" * 60)
        print("FLOP NETWORK COMMUNITY BOT STATUS")
        print("=" * 60)
        print(f"  Network Mode      : {self.config.network.upper()}")
        print(f"  RPC Node URL      : {self.config.rpc_url}")
        print(f"  Gateway API URL   : {self.config.gateway_url}")
        print(f"  Wallet Address    : {self.address}")
        
        # Test RPC
        try:
            chain_name = self.rpc.get_chain_name()
            print(f"  Substrate L1 Chain: {chain_name} (CONNECTED)")
        except Exception as exc:
            print(f"  Substrate L1 Chain: CONNECTION FAILED ({exc})")

        # Test Balance
        bal = self.rpc.get_wallet_balance(self.address)
        bal_str = f"{bal:,.4f} FLOP" if bal is not None else "0.0 FLOP (or unindexed)"
        print(f"  On-Chain Balance  : {bal_str}")

        # Test Gateway
        gw_ok = self.gateway.check_health()
        print(f"  Gateway Status    : {'ONLINE' if gw_ok else 'OFFLINE'}")

        # Check Enrollment
        token = self.gateway.get_cached_bearer(self.address)
        print(f"  Gateway Enrolled  : {'YES (Bearer cached)' if token else 'NO (Requires enrollment)'}")
        print(f"  Inference Model   : {self.config.flop_model}")
        print(f"  AI Task Builder   : {'ENABLED (' + self.config.ai_builder_model + ')' if self.config.ai_builder_enabled else 'DISABLED (Combinatorial)'}")
        print("=" * 60 + "\n")

        return {
            "network": self.config.network,
            "address": self.address,
            "balance": float(bal) if bal else 0.0,
            "gateway_online": gw_ok,
            "enrolled": bool(token),
        }

    def ensure_enrolled(self) -> str:
        """Ensure active gateway bearer token, enrolling if needed."""
        if not self._bearer_token:
            self._bearer_token = self.gateway.enroll_wallet(self.address, self.config.private_key_hex)
        return self._bearer_token

    def execute_cycle(self, category: str = "trade") -> bool:
        """Execute one complete task generation and inference cycle."""
        now = time.time()
        if now < self._cooldown_until:
            wait_s = round(self._cooldown_until - now, 1)
            logger.info("Bot in backoff cooldown (%0.1fs remaining). Waiting...", wait_s)
            time.sleep(min(wait_s, 5.0))
            return False

        # 1. Cached Balance Verification & Rate-Limited Auto-Faucet
        # Only query explorer if never checked or after 10 minutes (600s) to prevent 429 spam
        if self._cached_balance is None or (now - self._last_balance_check > 600.0):
            fetched_bal = self.rpc.get_wallet_balance(self.address)
            self._last_balance_check = now
            if fetched_bal is not None:
                self._cached_balance = fetched_bal
                logger.info("On-chain wallet balance: %0.4f FLOP", fetched_bal)
            elif self._cached_balance is None:
                # If explorer is rate-limited on startup, assume sufficient balance so we don't spam faucet
                logger.debug("Explorer balance check rate limited or unavailable, continuing with cached session.")

        # If balance was confirmed to be below minimum, trigger faucet with strict 1-hour cooldown
        min_bal = Decimal(str(self.config.min_required_balance_flop))
        if self._cached_balance is not None and self._cached_balance < min_bal:
            if now - self._last_faucet_attempt > 3600.0:
                logger.info(
                    "Wallet balance (%0.4f FLOP) is below required minimum (%s FLOP). Requesting faucet...",
                    self._cached_balance, self.config.min_required_balance_flop
                )
                self._last_faucet_attempt = now
                try:
                    claim_res = self.gateway.claim_faucet(self.address)
                    logger.info("Faucet claim response: %s", claim_res)
                    time.sleep(5.0)
                    new_bal = self.rpc.get_wallet_balance(self.address)
                    if new_bal is not None:
                        self._cached_balance = new_bal
                except Exception as f_err:
                    logger.warning("Auto-faucet claim failed or cooldown active: %s", f_err)

            if self._cached_balance < min_bal:
                logger.warning(
                    "Balance still below minimum (%s FLOP). Waiting for funding before running inference.",
                    self.config.min_required_balance_flop
                )
                self._cooldown_until = time.time() + 60.0
                return False

        # 2. Ensure gateway enrollment
        try:
            bearer = self.ensure_enrolled()
        except FlopCapReachedError as exc:
            retry_s = exc.retry_after or 900.0
            self._cooldown_until = time.time() + retry_s
            logger.warning("Gateway enrollment cap reached. Backing off for %.0fs: %s", retry_s, exc)
            return False
        except Exception as exc:
            logger.error("Enrollment failed: %s", exc)
            return False

        # 3. Generate Task
        task = self.ai_synthesizer.build_task(category=category)
        logger.info("Built task [%s]: %s", task.task_id, task.title)

        # 4. Dispatch Inference to FLOP Network
        start_ts = time.perf_counter()
        try:
            comp = self.gateway.chat_completion(
                bearer_token=bearer,
                model=self.config.flop_model,
                messages=task.to_messages(),
                max_tokens=350,
            )
        except FlopAuthError:
            logger.warning("Bearer token expired (HTTP 401). Invalidating cache and re-enrolling...")
            self.gateway.invalidate_cached_bearer(self.address)
            self._bearer_token = None
            return False
        except FlopRateLimitError as exc:
            backoff_s = exc.retry_after or 30.0
            self._cooldown_until = time.time() + backoff_s
            logger.warning("FLOP Gateway rate limited (429). Backing off for %0.1fs", backoff_s)
            return False
        except FlopNodeOverloadedError as exc:
            backoff_s = exc.retry_after or 45.0
            self._cooldown_until = time.time() + backoff_s
            logger.warning("FLOP GPU inference node busy/recovering (%s). Backing off for %0.1fs...", exc, backoff_s)
            return False
        except Exception as exc:
            logger.error("Inference execution failed: %s", exc)
            self._cooldown_until = time.time() + 30.0
            return False

        latency = (time.perf_counter() - start_ts) * 1000.0

        # 5. Process and Log Results
        choices = comp.get("choices", [])
        content = choices[0]["message"]["content"] if choices else ""
        usage = comp.get("usage", {})
        total_toks = usage.get("total_tokens", 0)
        prompt_toks = usage.get("prompt_tokens", 0)
        comp_toks = usage.get("completion_tokens", 0)

        logger.info(
            "SUCCESS! Task %s completed in %0.1fms | Tokens: %d (prompt: %d, completion: %d)",
            task.task_id, latency, total_toks, prompt_toks, comp_toks
        )
        logger.info("Model Output Excerpt: %s", content[:120].replace("\n", " ") + "...")

        # 6. Save Receipt
        self.log_receipt(
            task=task,
            model=comp.get("model", self.config.flop_model),
            total_tokens=total_toks,
            prompt_tokens=prompt_toks,
            completion_tokens=comp_toks,
            response_text=content,
            latency_ms=latency,
        )

        return True

    def run_loop(self, category: str = "trade") -> None:
        """Run continuous autonomous execution loop."""
        logger.info("Starting autonomous loop on %s (Interval: %0.1fs)...", self.config.network.upper(), self.config.loop_interval_seconds)
        while True:
            try:
                self.execute_cycle(category=category)
            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received. Shutting down cleanly.")
                break
            except Exception as exc:
                logger.error("Unexpected error during cycle: %s", exc)

            time.sleep(self.config.loop_interval_seconds)
