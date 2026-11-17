#!/usr/bin/env python3
"""
FLOP Network Community Bot — Command Line Interface.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Command-line interface for the FLOP Network bot.

Usage:
  python main.py --status             # Check network, balance, and gateway status
  python main.py --generate-wallet    # Generate a fresh Ed25519 wallet key
  python main.py --faucet             # Request faucet tokens for configured wallet
  python main.py --run-once           # Execute a single task generation & inference cycle
  python main.py --loop               # Run tasks continuously
  python main.py --category web3      # Run Web3 question task instead of trade decision
  python main.py --models             # List admitted models on the FLOP gateway
"""

from __future__ import annotations

import argparse
import sys
from config import BotConfig
from crypto import generate_new_wallet


def main() -> int:
    parser = argparse.ArgumentParser(description="FLOP Network Community Bot")
    parser.add_argument("--status", action="store_true", help="Display full network, wallet, and gateway diagnostics")
    parser.add_argument("--generate-wallet", action="store_true", help="Generate a fresh Ed25519 wallet key and SS58 address")
    parser.add_argument("--faucet", action="store_true", help="Request faucet funds for your configured wallet")
    parser.add_argument("--enroll", action="store_true", help="Enroll wallet with FLOP Gateway and cache Bearer token")
    parser.add_argument("--run-once", action="store_true", help="Execute 1 task generation and inference cycle")
    parser.add_argument("--loop", action="store_true", help="Run tasks continuously")
    parser.add_argument("--category", choices=["trade", "web3"], default="trade", help="Task category (trade | web3, default: trade)")
    parser.add_argument("--models", action="store_true", help="List available inference models on the FLOP gateway")

    args = parser.parse_args()

    # 1. Wallet Generation (does not require .env configuration)
    if args.generate_wallet:
        priv_hex, ss58_addr = generate_new_wallet()
        print("\n" + "=" * 60)
        print("NEW FLOP NETWORK WALLET GENERATED")
        print("=" * 60)
        print(f"  SS58 Address (Format 42): {ss58_addr}")
        print(f"  Private Key (Hex)       : {priv_hex}")
        print("-" * 60)
        print("To use this wallet, copy the private key into your .env file:")
        print(f"FLOP_PRIVATE_KEY={priv_hex}")
        print("=" * 60 + "\n")
        return 0

    # 2. Load Configuration
    config = BotConfig.load()

    # If user hasn't configured a key yet, display guidance
    if not config.private_key_hex:
        print("\n[ERROR] No FLOP_PRIVATE_KEY found in .env!")
        print("Run `python main.py --generate-wallet` to generate a new key, or")
        print("copy your existing Ed25519 private key into `.env`.")
        print("Example: FLOP_PRIVATE_KEY=3a1b...\n")
        return 1

    from bot import FlopCommunityBot
    bot = FlopCommunityBot(config)

    # 3. Handle Actions
    if args.status:
        bot.print_status()
        return 0

    if args.models:
        print(f"\nQuerying active models on FLOP {config.network.upper()} ({config.gateway_url})...")
        try:
            models = bot.gateway.list_models()
            print("\nAvailable Models:")
            print("-" * 50)
            for m in models:
                mid = m.get("id") if isinstance(m, dict) else str(m)
                print(f"  - {mid}")
            print("-" * 50 + "\n")
        except Exception as exc:
            print(f"[ERROR] Could not fetch models: {exc}")
        return 0

    if args.faucet:
        print(f"\nRequesting faucet funding for {bot.address} on {config.network.upper()}...")
        try:
            res = bot.gateway.claim_faucet(bot.address)
            print("Faucet response:", res)
        except Exception as exc:
            print(f"[ERROR] Faucet claim failed: {exc}")
        return 0

    if args.enroll:
        print(f"\nEnrolling wallet {bot.address} with FLOP Gateway ({config.gateway_url})...")
        try:
            token = bot.gateway.enroll_wallet(bot.address, config.private_key_hex)
            print(f"SUCCESS! Wallet enrolled. Bearer key cached in data/bearer_cache.json")
            print(f"Bearer Token Preview: {token[:16]}...")
        except Exception as exc:
            print(f"[ERROR] Enrollment failed: {exc}")
        return 0

    if args.run_once:
        print(f"\nExecuting single cycle for category '{args.category}'...")
        success = bot.execute_cycle(category=args.category)
        return 0 if success else 1

    if args.loop:
        bot.run_loop(category=args.category)
        return 0

    # Default action if no flag passed
    bot.print_status()
    print("Run `python main.py --help` for available commands.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
