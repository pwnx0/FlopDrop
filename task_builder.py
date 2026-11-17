"""
Task Builders: Trade Decisions & Modular Web3 Question Framework.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Provides:
1. BaseTask & BaseTaskBuilder: Abstract modular task contracts.
2. TradeDecisionTaskBuilder: Prebuilt decision tasks evaluating market structure,
   derivatives context, trade direction, invalidation, profit targets, and risk scores.
3. Web3CustomTaskBuilder: Dedicated template for user-defined Web3 questions
   (contract audits, token economics, on-chain governance, event decoding).
"""

from __future__ import annotations

import abc
import hashlib
import json
import random
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class BaseTask:
    """Standard task payload consumed by FLOP Gateway inference."""
    task_id: str
    category: str
    title: str
    system_prompt: str
    user_prompt: str
    questions: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_messages(self) -> List[Dict[str, str]]:
        """Format task into OpenAI-compatible chat messages."""
        return [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.user_prompt},
        ]


class BaseTaskBuilder(abc.ABC):
    """Abstract interface for all task generators."""

    @abc.abstractmethod
    def generate_task(self, seed: Optional[str] = None) -> BaseTask:
        """Generate a task instance."""
        pass


# ==============================================================================
# 1. Trade Decision Task Builder (Prebuilt Market Evaluation Benchmark)
# ==============================================================================

TRADE_ASSETS = [
    "BTC", "ETH", "SOL", "FLOP", "TAO", "RENDER", "SUI", "NEAR", "AVAX", "LINK",
    "ARB", "OP", "MATIC", "INJ", "TIA", "SEI", "APT", "UNI", "AAVE", "MKR"
]

TRADE_TIMEFRAMES = ["5m", "15m", "1h", "4h", "1D"]

TECHNICAL_STRUCTURES = [
    "Monday Low Liquidity Sweep and Reclaim of Range Value Area Low",
    "Monday High Liquidity Sweep with Bearish Swing Failure Pattern (SFP)",
    "Bullish Order Block retest at 0.618 Fibonacci equilibrium",
    "Fair Value Gap (FVG) inversion on expanding market buy volume",
    "Wyckoff Spring below accumulation range low with heavy volume absorption",
    "Ascending triangle compression against overhead weekly resistance",
    "High timeframe support flip to confirmed resistance with volume dry-up",
    "Cumulative Volume Delta (CVD) absorption at key psychological level",
]

DERIVATIVES_STATES = [
    "Negative funding rate (-0.03%) with aggressive short open interest expansion",
    "Positive funding rate (+0.05%) with over-leveraged long open interest building",
    "Spot CVD aggressively leading while perpetual futures funding remains neutral",
    "Long-to-short ratio skewed 3:1 bullish with perpetual discount against spot index",
    "Basis divergence: futures premium blowing out 40 bps above spot price",
    "Open Interest wipeout cascade into stacked resting demand liquidity",
]

RISK_MANDATES = [
    {"name": "Capital Preservation", "risk_tolerance": "Conservative", "max_invalidation_pct": 1.5},
    {"name": "Trend Momentum", "risk_tolerance": "Moderate", "max_invalidation_pct": 3.0},
    {"name": "Mean Reversion", "risk_tolerance": "Aggressive", "max_invalidation_pct": 4.5},
]


class TradeDecisionTaskBuilder(BaseTaskBuilder):
    """Prebuilt task builder evaluating trade decisions and risk frameworks."""

    def __init__(self) -> None:
        self._counter = 0

    def generate_task(self, seed: Optional[str] = None) -> BaseTask:
        self._counter += 1
        seed_str = seed or f"{time.time()}:{self._counter}:{random.random()}"
        rnd = random.Random(seed_str)

        asset = rnd.choice(TRADE_ASSETS)
        timeframe = rnd.choice(TRADE_TIMEFRAMES)
        structure = rnd.choice(TECHNICAL_STRUCTURES)
        derivatives = rnd.choice(DERIVATIVES_STATES)
        mandate = rnd.choice(RISK_MANDATES)

        # Baseline price estimates
        base_prices = {"BTC": 68000.0, "ETH": 3400.0, "SOL": 180.0, "FLOP": 1.25, "TAO": 480.0}
        base_price = base_prices.get(asset, 10.0 + (hash(asset) % 50))
        price = round(base_price * (1.0 + (rnd.random() - 0.5) * 0.1), 2)

        scenario_desc = (
            f"Asset: {asset}/USDT on {timeframe} timeframe at ${price:,.2f}. "
            f"Technical Structure: {structure}. "
            f"Derivatives Context: {derivatives}. "
            f"Operating Mandate: {mandate['name']} ({mandate['risk_tolerance']}, max invalidation {mandate['max_invalidation_pct']}%)."
        )

        questions = {
            "trade_call": {
                "type": "choice",
                "options": ["long", "short", "neutral_cash"],
                "instruction": "Determine the highest expected-value trade action.",
            },
            "stop_loss": {
                "type": "price_level",
                "tight_invalidation": round(price * (1.0 - mandate["max_invalidation_pct"] / 100), 2),
                "instruction": "Define optimal stop-loss price for invalidation.",
            },
            "profit_target": {
                "type": "price_level",
                "tp1": round(price * 1.03, 2),
                "tp2": round(price * 1.06, 2),
                "instruction": "Set primary and runner take-profit levels.",
            },
            "risk_score": {
                "type": "numeric_range",
                "scale": "0.0 (safest) to 1.0 (highest volatility / gamble)",
                "instruction": "Score overall setup execution risk.",
            },
        }

        user_prompt = (
            f"Analyze the following market setup and output your decision strictly in JSON format:\n\n"
            f"{scenario_desc}\n\n"
            f"Required Output JSON Schema:\n"
            f"{{\n"
            f'  "action": "long" | "short" | "neutral_cash",\n'
            f'  "invalidation_price": float,\n'
            f'  "take_profit_price": float,\n'
            f'  "risk_score": float,\n'
            f'  "thesis_summary": string\n'
            f"}}"
        )

        task_id = f"trade_{hashlib.sha256(seed_str.encode()).hexdigest()[:12]}"

        return BaseTask(
            task_id=task_id,
            category="trade_decision",
            title=f"Trade Decision: {asset} ({timeframe}) - {mandate['name']}",
            system_prompt=(
                "You are an institutional quantitative trading agent. "
                "Evaluate market microstructure, invalidation thresholds, and risk-reward ratios. "
                "Respond strictly with the requested JSON analysis."
            ),
            user_prompt=user_prompt,
            questions=questions,
            metadata={
                "asset": asset,
                "timeframe": timeframe,
                "price": price,
                "mandate": mandate["name"],
            },
        )


# ==============================================================================
# 2. Web3 Custom Task Builder (Modular Template for User Web3 Questions)
# ==============================================================================

WEB3_DOMAINS = [
    "Smart Contract Security & Reentrancy",
    "AMM Liquidity Pool Invariant Math",
    "Cross-Chain Bridge Message Verification",
    "MEV & Slippage Protection Analysis",
    "Decentralized Governance Proposal Review",
]


class Web3CustomTaskBuilder(BaseTaskBuilder):
    """
    Modular Task Builder for Web3 Questions.
    
    Add custom contract analysis, on-chain telemetry, or protocol questions here.
    """

    def __init__(self) -> None:
        self._counter = 0

    def generate_task(self, seed: Optional[str] = None) -> BaseTask:
        self._counter += 1
        seed_str = seed or f"{time.time()}:web3:{self._counter}"
        rnd = random.Random(seed_str)

        domain = rnd.choice(WEB3_DOMAINS)

        # ----------------------------------------------------------------------
        # Add or customize Web3 question formats here.
        # ----------------------------------------------------------------------
        if "Security" in domain:
            code_snippet = (
                "function withdraw(uint256 amount) external {\n"
                "    require(balances[msg.sender] >= amount, 'Insufficient');\n"
                "    (bool success, ) = msg.sender.call{value: amount}('');\n"
                "    require(success, 'Transfer failed');\n"
                "    balances[msg.sender] -= amount;\n"
                "}"
            )
            question_text = (
                f"Analyze the following smart contract function for security vulnerabilities:\n\n"
                f"```solidity\n{code_snippet}\n```\n\n"
                f"Identify the primary vulnerability (e.g., checks-effects-interactions violation), "
                f"severity (LOW/MEDIUM/HIGH/CRITICAL), and the recommended secure rewrite in JSON."
            )
        else:
            question_text = (
                f"Subject: {domain}\n"
                f"Calculate the constant product formula delta (x * y = k) for a 50 ETH swap into a "
                f"pool containing 1,000 ETH and 3,000,000 USDC. Determine slippage percentage, "
                f"effective execution price, and output your derivation in JSON."
            )

        task_id = f"web3_{hashlib.sha256(seed_str.encode()).hexdigest()[:12]}"

        return BaseTask(
            task_id=task_id,
            category="web3_analysis",
            title=f"Web3 Protocol Verification: {domain}",
            system_prompt=(
                "You are an expert blockchain systems engineer and Web3 auditor. "
                "Analyze protocols, code, and on-chain mechanics with rigorous technical precision."
            ),
            user_prompt=question_text,
            questions={"domain": domain},
            metadata={"domain": domain},
        )
